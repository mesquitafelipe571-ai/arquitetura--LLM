import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("setup", REPO / "scripts/setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

class SetupTests(unittest.TestCase):
    def test_codex_decisao_agent_disables_shell_and_extensions(self):
        # O perfil Codex herda as ferramentas da sessão; sem shell, um item injetado não roda comandos.
        import tomllib
        data = tomllib.loads((REPO / ".codex/agents/decisao.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["features"], {"shell_tool": False, "apps": False, "plugins": False,
                                            "request_permissions_tool": False})

    def test_codex_decisao_skill_requires_session_without_rea(self):
        # O agente herda os MCPs da sessão: com itens de terceiros, só numa sessão sem o REA.
        skill = (REPO / ".agents/skills/decisao/SKILL.md").read_text(encoding="utf-8")
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        for text in (skill, readme):
            self.assertIn("codex -c mcp_servers.rea.enabled=false", text)
        import tomllib
        config = tomllib.loads((REPO / ".codex/config.toml").read_text(encoding="utf-8"))
        self.assertIn("rea", config["mcp_servers"])  # o comando acima desliga um servidor que existe

    def test_decisao_agent_has_closed_tool_list(self):
        # Sem `tools` o subagente herda Bash/Write/WebFetch/MCPs; um item injetado agiria com eles.
        text = (REPO / ".claude/agents/decisao.md").read_text(encoding="utf-8")
        front = text.split("---", 2)[1]
        line = next(l for l in front.splitlines() if l.startswith("tools:"))
        tools = {t.strip() for t in line.split(":", 1)[1].split(",")}
        self.assertEqual(tools, {"Read", "Glob", "Grep", "mcp__ollaya__decide",
                                 "mcp__ollaya__list_models", "mcp__ollaya__show_model"})

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "runtime"
        self.root.mkdir()
        setup.initialize(self.root)

    def checkout(self, component_id="ecc"):
        work = self.base / ("fixture-" + component_id)
        work.mkdir()
        (work / "LICENSE").write_text("MIT fixture\n")
        skill = work / "skills/demo"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\n---\nTest skill\n")
        setup.capture(["git", "init", "--quiet", work])
        setup.capture(["git", "-C", work, "add", "."])
        setup.capture(["git", "-C", work, "-c", "user.name=Fixture", "-c", "user.email=test@example.invalid",
                       "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"])
        sha = setup.capture(["git", "-C", work, "rev-parse", "HEAD"])
        c = {"id": component_id, "repository": "fixture/repo", "commit": sha, "skills": ["demo"], "license": "MIT"}
        setup.capture(["git", "-C", work, "remote", "add", "origin", "https://github.com/fixture/repo.git"])
        target = setup.source_path(self.root, c)
        target.parent.mkdir(parents=True)
        work.rename(target)
        return c, target

    def test_init_preserves_distinct_private_secrets(self):
        env = self.root / "config/paperclip.env"
        before = env.read_bytes()
        setup.initialize(self.root)
        self.assertEqual(before, env.read_bytes())
        self.assertEqual(env.stat().st_mode & 0o777, 0o600)
        values = dict(line.split("=", 1) for line in env.read_text().splitlines() if "=" in line)
        self.assertNotEqual(values["BETTER_AUTH_SECRET"], values["PAPERCLIP_TOOL_ACTION_SIGNING_SECRET"])
        self.assertEqual(len(values["BETTER_AUTH_SECRET"]), 64)

    def test_missing_secrets_with_existing_database_fails(self):
        (self.root / "config/paperclip.env").unlink()
        (self.root / "data/paperclip/database-marker").write_text("existing")
        with self.assertRaisesRegex(ValueError, "restaure"):
            setup.initialize(self.root)
        self.assertFalse((self.root / "config/paperclip.env").exists())

    def test_runtime_symlink_rejected(self):
        root = self.base / "other-runtime"
        root.mkdir()
        (root / "config").symlink_to(self.root / "config", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            setup.initialize(root)

    def test_concurrent_invocation_is_rejected(self):
        with setup.mutation_lock(self.root):
            with self.assertRaisesRegex(ValueError, "Outra operação"):
                with setup.mutation_lock(self.root):
                    pass

    def test_sync_existing_exact_checkout_is_idempotent(self):
        c, path = self.checkout()
        self.assertEqual(setup.sync_component(self.root, c)["status"], "already_present")
        self.assertTrue(path.is_dir())

    def test_sync_preserves_dirty_checkout(self):
        c, path = self.checkout()
        file = path / "skills/demo/SKILL.md"
        file.write_text("user modification")
        with self.assertRaisesRegex(ValueError, "alterações"):
            setup.sync_component(self.root, c)
        self.assertEqual(file.read_text(), "user modification")

    def test_untracked_and_ignored_content_is_rejected(self):
        c, path = self.checkout()
        extra = path / "skills/demo/extra.py"
        extra.write_text("unexpected")
        with self.assertRaisesRegex(ValueError, "alterações"):
            setup.verify_source(path, c)
        extra.unlink()
        (path / ".git/info/exclude").write_text("ignored.txt\n")
        (path / "ignored.txt").write_text("not part of commit")
        with self.assertRaisesRegex(ValueError, "alterações"):
            setup.verify_source(path, c)

    def test_license_collision_is_detected_before_copy(self):
        c, _ = self.checkout()
        project = self.base / "project"
        (project / ".agents").mkdir(parents=True)
        (project / ".agents/upstream-licenses").symlink_to(self.base)
        with self.assertRaisesRegex(ValueError, "symlink"):
            setup.export_skills(self.root, c, project, ["demo"])
        self.assertFalse((project / ".agents/skills/demo").exists())

    def test_wrong_origin_is_rejected(self):
        c, path = self.checkout()
        setup.capture(["git", "-C", path, "remote", "set-url", "origin", "https://github.com/other/repo.git"])
        with self.assertRaisesRegex(ValueError, "Origem"):
            setup.verify_source(path, c)

    def test_failed_parallel_task_does_not_hide_success(self):
        components = [{"id": "one"}, {"id": "two"}]
        def sync(root, c):
            if c["id"] == "two":
                raise ValueError("offline")
            return {"component": "one", "status": "already_present"}
        with patch.object(setup, "sync_component", side_effect=sync):
            results = setup.sync_all(self.root, components, 2)
        self.assertEqual([r["status"] for r in results], ["already_present", "failed"])
        self.assertEqual(json.loads((self.root / "state/sync.json").read_text())["results"], results)

    def test_skill_export_keeps_instructions_and_license(self):
        c, _ = self.checkout()
        project = self.base / "project"
        project.mkdir()
        (project / "AGENTS.md").write_text("Keep my rules\n")
        result = setup.export_skills(self.root, c, project, ["demo"])
        self.assertEqual(result["skills"], ["demo"])
        self.assertEqual((project / "AGENTS.md").read_text(), "Keep my rules\n")
        self.assertTrue((project / ".agents/skills/demo/SKILL.md").is_file())
        self.assertTrue(list((project / ".agents/upstream-licenses").glob("*.txt")))
        setup.export_skills(self.root, c, project, ["demo"])

    def test_skill_collision_preserves_existing_file(self):
        c, _ = self.checkout()
        project = self.base / "project"
        dest = project / ".agents/skills/demo"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("Existing content")
        with self.assertRaisesRegex(ValueError, "Colisão"):
            setup.export_skills(self.root, c, project, ["demo"])
        self.assertEqual((dest / "SKILL.md").read_text(), "Existing content")

    def test_skill_symlink_is_rejected(self):
        c, _ = self.checkout()
        project = self.base / "project"
        project.mkdir()
        (project / ".agents").symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            setup.export_skills(self.root, c, project, ["demo"])

    def test_unlisted_skill_is_rejected(self):
        c, _ = self.checkout()
        project = self.base / "project"
        project.mkdir()
        with self.assertRaisesRegex(ValueError, "catálogo"):
            setup.export_skills(self.root, c, project, ["../../other"])

    def test_compose_preserves_nonsecret_paths_under_sudo(self):
        c, path = self.checkout("paperclip")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "not-for-this-deployment"}):
            cmd, env = setup.compose(self.root, c, True)
        self.assertEqual(cmd[:2], ["sudo", "env"])
        self.assertIn("ALM_PAPERCLIP_SOURCE=" + str(path), cmd)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("not-for-this-deployment", " ".join(cmd))
        self.assertIn(str(self.root / "config/paperclip.env"), cmd)

    def test_health_starting_is_not_ready(self):
        response = io.BytesIO(b'{"status":"starting"}')
        with patch.object(setup.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "pronto"):
                setup.health()

    def test_health_ready_is_accepted_and_filtered(self):
        response = io.BytesIO(b'{"status":"ok","commit":"abc","private":"hidden"}')
        with patch.object(setup.urllib.request, "urlopen", return_value=response):
            self.assertEqual(setup.health(), {"status": "ok", "commit": "abc"})

    def test_compose_bound_to_loopback_and_production(self):
        cfg = json.loads((REPO / "compose.paperclip.json").read_text())["services"]["paperclip"]
        self.assertEqual(cfg["ports"], ["127.0.0.1:3100:3100"])
        self.assertEqual(cfg["build"]["target"], "production")
        self.assertEqual(cfg["environment"]["PAPERCLIP_DEPLOYMENT_MODE"], "authenticated")
        self.assertNotIn("/var/run/docker.sock", json.dumps(cfg))

    def test_plan_has_no_runtime_side_effect(self):
        nonexistent = self.base / "plan-only"
        result = subprocess.run([os.sys.executable, str(REPO / "scripts/setup.py"),
                                 "--root", str(nonexistent), "plan"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(nonexistent.exists())
        self.assertFalse(json.loads(result.stdout)["cloud_chats_connected"])

    def test_backup_resumes_original_container_and_uses_original_image(self):
        c, _ = self.checkout("paperclip")
        def capture(argv, **kwargs):
            if "ps" in argv:
                return "existing-container"
            if "{{json .Mounts}}" in argv:
                return json.dumps([{"Type": "bind", "Source": str(self.root / "data/paperclip"), "Destination": "/paperclip"}])
            if "{{.Image}}" in argv:
                return "sha256:original-image"
            if '{{index .Config.Labels "org.opencontainers.image.revision"}}' in argv:
                return c["commit"]
            if "{{.State.Running}}" in argv:
                return "true"
            if "{{.State.Health.Status}}" in argv:
                return "healthy"
            raise AssertionError(argv)
        with patch.object(setup, "verify_source"), patch.object(setup, "capture", side_effect=capture), patch.object(setup, "run") as run:
            result = setup.paperclip(self.root, c, False, "backup")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(["docker", "start", "existing-container"], commands)
        helper = next(cmd for cmd in commands if "tar" in cmd)
        self.assertIn("sha256:original-image", helper)
        self.assertIn("type=bind,src=" + str(self.root / "data/paperclip") + ",dst=/data,readonly", helper)
        self.assertFalse(any("up" in cmd or "build" in cmd for cmd in commands))
        manifest = json.loads((Path(result["backup"]) / "manifest.json").read_text())
        self.assertEqual(manifest["image_id"], "sha256:original-image")

    def test_status_does_not_regenerate_lost_configuration(self):
        (self.root / "config/paperclip.env").unlink()
        result = subprocess.run([os.sys.executable, str(REPO / "scripts/setup.py"),
                                 "--root", str(self.root), "paperclip", "status"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.root / "config/paperclip.env").exists())

    def test_distinct_roots_use_distinct_compose_projects(self):
        c, _ = self.checkout("paperclip")
        cmd1, _ = setup.compose(self.root, c, False)
        other = self.base / "other"
        other.mkdir()
        setup.initialize(other)
        with patch.object(setup, "verify_source"):
            cmd2, _ = setup.compose(other, c, False)
        self.assertNotEqual(cmd1[cmd1.index("--project-name") + 1], cmd2[cmd2.index("--project-name") + 1])

    def test_pull_records_verified_official_digest(self):
        c, _ = self.checkout("paperclip")
        image_id = "sha256:" + "a" * 64
        digest = "ghcr.io/" + c["repository"] + "@sha256:" + "b" * 64
        def capture(argv, **kwargs):
            if "{{.Id}}" in argv:
                return image_id
            if "{{json .RepoDigests}}" in argv:
                return json.dumps([digest])
            return c["commit"]
        with patch.object(setup, "verify_source"), patch.object(setup, "capture", side_effect=capture), patch.object(setup, "run") as run:
            result = setup.paperclip(self.root, c, False, "pull")
        self.assertEqual(result["source_image_digest"], digest)
        self.assertEqual(result["method"], "official-image")
        self.assertEqual(json.loads((self.root / "state/paperclip-build.json").read_text()), result)
        self.assertTrue(any("tag" in call.args[0] for call in run.call_args_list))

    def test_pull_rejects_wrong_revision_without_activation(self):
        c, _ = self.checkout("paperclip")
        with patch.object(setup, "verify_source"), patch.object(setup, "capture", return_value="0" * 40), patch.object(setup, "run") as run:
            with self.assertRaisesRegex(ValueError, "Revisão"):
                setup.paperclip(self.root, c, False, "pull")
        self.assertFalse((self.root / "state/paperclip-build.json").exists())
        self.assertFalse(any("tag" in call.args[0] for call in run.call_args_list))

    def test_pull_requires_registry_digest(self):
        c, _ = self.checkout("paperclip")
        def capture(argv, **kwargs):
            return "[]" if "{{json .RepoDigests}}" in argv else c["commit"]
        with patch.object(setup, "verify_source"), patch.object(setup, "capture", side_effect=capture), patch.object(setup, "run") as run:
            with self.assertRaisesRegex(ValueError, "digest"):
                setup.paperclip(self.root, c, False, "pull")
        self.assertFalse(any("tag" in call.args[0] for call in run.call_args_list))

    def test_compose_appends_environment_override(self):
        c, _ = self.checkout("paperclip")
        overlay = self.base / "overlay.json"
        overlay.write_text('{"services":{}}')
        cmd, _ = setup.compose(self.root, c, False, overlay)
        self.assertEqual(cmd[-2:], ["-f", str(overlay.resolve())])
        self.assertIn(str(REPO / "compose.paperclip.json"), cmd)

    def test_compose_rejects_invalid_or_symlink_override(self):
        c, _ = self.checkout("paperclip")
        overlay = self.base / "missing.json"
        with self.assertRaisesRegex(ValueError, "Override"):
            setup.compose(self.root, c, False, overlay)
        target = self.base / "target.json"
        target.write_text("{}")
        overlay.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "Override"):
            setup.compose(self.root, c, False, overlay)

    def test_manifest_pins_and_candidate_not_default(self):
        c = setup.load_components()
        self.assertEqual(len(c), 5)
        self.assertEqual(c["ui-ux-pro-max"]["identity"], "candidate")
        self.assertEqual(sum(v["identity"] == "verified" for v in c.values()), 4)

if __name__ == "__main__":
    unittest.main()
