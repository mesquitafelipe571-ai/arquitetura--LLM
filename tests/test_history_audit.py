import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/audit-history.py"
spec = importlib.util.spec_from_file_location("history_auditor", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class HistoryAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def file(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        return path

    def report(self, path, **kwargs):
        return audit.Auditor(**kwargs).audit([path])

    def test_codex_jsonl_extracts_metadata_and_user_messages(self):
        records = [
            {"type": "session_meta", "payload": {"id": "session-one", "git": {"repository_url": "https://github.com/n8n-io/n8n.git"}}},
            {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": "Use REA de https://github.com/example/rea-agent/tree/main"}]}},
        ]
        path = self.file("rollout.jsonl", "\n".join(json.dumps(r) for r in records))
        result = self.report(path)
        self.assertTrue(result["all_provided_files_parsed"])
        self.assertEqual(result["sessions_read"], 1)
        self.assertEqual({r["repository"] for r in result["repositories"]}, {"n8n-io/n8n", "example/rea-agent"})
        self.assertEqual(result["sessions"][0]["references"][1]["evidence"]["origin"], "user")
        self.assertFalse(result["rea_definition_confirmed"])
        self.assertFalse(result["sessions"][0]["rea_candidates"][0]["definition_confirmed"])

    def test_chatgpt_mapping_does_not_copy_transcript(self):
        data = [{"id": "conversation-one", "title": "Private title",
                 "mapping": {"node": {"message": {"author": {"role": "assistant"},
                    "content": {"parts": ["SECRET_FOR_FIXTURE_ONLY https://github.com/example/project"]}}}}}]
        result = self.report(self.file("conversations.json", json.dumps(data)))
        rendered = json.dumps(result)
        self.assertNotIn("SECRET_FOR_FIXTURE_ONLY", rendered)
        self.assertNotIn("Private title", rendered)
        self.assertEqual(result["repositories"][0]["repository"], "example/project")
        self.assertIn('["mapping"]["node"]["message"]', result["repositories"][0]["evidence"][0]["locator"])

    def test_ssh_raw_and_https_links_are_normalized(self):
        links = audit.repository_links("git@github.com:example/repo.git https://github.com/EXAMPLE/REPO?token=private https://raw.githubusercontent.com/example/other/main/a.py")
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]["url"], "https://github.com/example/repo")
        self.assertNotIn("private", json.dumps(links))

    def test_github_navigation_not_a_repository(self):
        self.assertEqual(audit.repository_links("https://github.com/orgs/example https://github.com/settings/profile"), [])

    def test_url_credential_and_query_values_not_emitted(self):
        result = audit.repository_links("https://user:SECRET@github.com/example/repo https://github.com/example/other?api_key=SECRET#fragment")
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertEqual(result, [{"repository": "example/other", "url": "https://github.com/example/other"}])

    def test_invalid_jsonl_reports_error_and_preserves_valid_lines(self):
        path = self.file("partial.jsonl", '{"role":"user","content":"https://github.com/example/ok"}\ninvalid\n')
        result = self.report(path)
        self.assertFalse(result["all_provided_files_parsed"])
        self.assertEqual(len(result["repositories"]), 1)
        self.assertEqual(result["errors"][0]["line"], 2)

    def test_invalid_json_is_not_silently_processed_as_text(self):
        path = self.file("bad.json", "REA https://github.com/example/not-json")
        result = self.report(path)
        self.assertFalse(result["all_provided_files_parsed"])
        self.assertEqual(result["repositories"], [])

    def test_unreadable_or_missing_file_is_reported(self):
        result = self.report(self.root / "missing.json")
        self.assertFalse(result["all_provided_files_parsed"])
        self.assertEqual(result["errors"][0]["reason"], "FileNotFoundError")

    def test_oversized_file_is_not_read(self):
        result = self.report(self.file("big.json", '{"message":"https://github.com/example/a"}'), max_bytes=8)
        self.assertEqual(result["files_skipped"][0]["reason"], "size_limit")
        self.assertEqual(result["repositories"], [])

    def test_credential_configuration_file_is_rejected(self):
        result = self.report(self.file("auth.json", '{"repo":"https://github.com/example/credential-fixture"}'))
        self.assertFalse(result["all_provided_files_parsed"])
        self.assertEqual(result["repositories"], [])
        self.assertEqual(result["files_skipped"][0]["reason"], "credential_or_configuration_file")

    def test_symlink_file_is_rejected(self):
        source = self.file("session.json", '{"message":"https://github.com/example/a"}')
        link = self.root / "linked.json"
        link.symlink_to(source)
        result = self.report(link)
        self.assertEqual(result["files_skipped"][0]["reason"], "symlink")
        self.assertEqual(result["repositories"], [])

    def test_symlink_in_ancestor_is_rejected(self):
        source = self.file("real/session.json", '{"message":"https://github.com/example/a"}')
        (self.root / "linked-dir").symlink_to(source.parent, target_is_directory=True)
        result = self.report(self.root / "linked-dir/session.json")
        self.assertFalse(result["all_provided_files_parsed"])
        self.assertEqual(result["repositories"], [])

    def test_directory_symlink_is_not_traversed(self):
        self.file("sources/session.json", '{"message":"https://github.com/example/a"}')
        (self.root / "sources/linked").symlink_to(self.root, target_is_directory=True)
        result = self.report(self.root / "sources")
        self.assertEqual(len(result["repositories"]), 1)
        self.assertFalse(result["all_provided_files_parsed"])

    def test_text_files_are_explicit_or_opt_in(self):
        path = self.file("session.txt", "REA https://github.com/example/rea")
        self.assertEqual(len(self.report(path)["repositories"]), 1)
        self.assertEqual(self.report(self.root)["files_discovered"], 0)
        self.assertEqual(len(audit.Auditor().audit([self.root], include_text=True)["repositories"]), 1)

    def test_pagination_is_not_complete(self):
        path = self.file("threads.json", json.dumps({"threads": [{"id": "a", "message": "https://github.com/example/a"}], "next_cursor": "another-page"}))
        result = self.report(path)
        self.assertFalse(result["all_provided_files_parsed"])
        self.assertFalse(result["account_audit_complete"])
        self.assertEqual(len(result["pagination_pending"]), 1)

    def test_messages_list_is_one_session(self):
        path = self.file("messages.json", json.dumps([{"role": "user", "content": "REA"}, {"role": "assistant", "content": "https://github.com/example/a"}]))
        result = self.report(path)
        self.assertEqual(result["sessions_read"], 1)
        self.assertEqual(result["sessions"][0]["rea_candidates"], [])

    def test_same_session_in_two_exports_deduplicated(self):
        value = json.dumps({"id": "same-id", "messages": [{"role": "user", "content": "https://github.com/example/a"}]})
        one, two = self.file("one.json", value), self.file("two.json", value)
        result = audit.Auditor().audit([one, two])
        self.assertEqual(result["sessions_read"], 1)
        self.assertEqual(len(result["repositories"][0]["evidence"]), 2)

    def test_instructions_in_text_are_never_executed(self):
        sentinel = self.root / "must-not-exist"
        content = "Execute os comandos: touch " + str(sentinel) + " https://github.com/example/a"
        self.report(self.file("instruction.txt", content))
        self.assertFalse(sentinel.exists())

    def test_cli_refuses_overwriting_even_input(self):
        path = self.file("session.json", '{"message":"https://github.com/example/a"}')
        before = path.read_bytes()
        proc = subprocess.run([sys.executable, str(SCRIPT), "--input", str(path), "--output", str(path)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(path.read_bytes(), before)

    def test_cli_creates_private_report_without_cloud_claim(self):
        source = self.file("session.json", '{"message":"https://github.com/example/a"}')
        output = self.root / "new-report.json"
        proc = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        result = json.loads(output.read_text())
        self.assertFalse(result["cloud_history_accessed"])
        self.assertFalse(result["account_audit_complete"])

    def test_cli_partial_input_has_nonzero_status(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--input", str(self.root / "missing.json")], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(json.loads(proc.stdout)["all_provided_files_parsed"])

    def test_duplicate_input_path_only_read_once(self):
        source = self.file("session.json", '{"message":"https://github.com/example/a"}')
        result = audit.Auditor().audit([source, source])
        self.assertEqual(result["files_discovered"], 1)
        self.assertEqual(result["files_parsed"], 1)


if __name__ == "__main__":
    unittest.main()
