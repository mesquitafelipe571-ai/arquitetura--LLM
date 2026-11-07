"""Regressões das correções locais nas skills de anthropics/skills (ver .agents/anthropic-skills/SOURCE.md)."""
import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import textwrap
import unittest

SKILLS = Path(__file__).resolve().parents[1] / ".agents/skills"
HAS_DEFUSEDXML = importlib.util.find_spec("defusedxml") is not None


def run_in(scripts_dir, code):
    """Roda o trecho com o diretório de scripts da skill no sys.path, como os scripts esperam."""
    prelude = f"import sys; sys.path.insert(0, {str(scripts_dir)!r})\n"
    return subprocess.run([sys.executable, "-c", prelude + textwrap.dedent(code)],
                          capture_output=True, text=True, timeout=60)


@unittest.skipUnless(HAS_DEFUSEDXML, "defusedxml não instalado")
class OfficeSkillTests(unittest.TestCase):
    def test_pptx_clean_keeps_slides_listed_with_other_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ppt/_rels").mkdir(parents=True)
            (root / "ppt/slides").mkdir()
            (root / "ppt/presentation.xml").write_text(
                '<x:presentation xmlns:x="http://schemas.openxmlformats.org/presentationml/2006/main"'
                ' xmlns:rel="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<x:sldIdLst><x:sldId id="256" rel:id="rId2"/></x:sldIdLst></x:presentation>')
            (root / "ppt/_rels/presentation.xml.rels").write_text(
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/slide" Target="slides/slide1.xml"/></Relationships>')
            (root / "ppt/slides/slide1.xml").write_text("<x/>")
            result = run_in(SKILLS / "pptx/scripts", f"""
                from pathlib import Path
                from clean import remove_orphaned_slides
                print(remove_orphaned_slides(Path({tmp!r})))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "[]")
            self.assertTrue((root / "ppt/slides/slide1.xml").exists())

    def test_docx_accept_changes_timeout_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.docx"
            src.write_bytes(b"x")
            result = run_in(SKILLS / "docx/scripts", f"""
                import subprocess
                from unittest import mock
                import accept_changes
                with mock.patch.object(accept_changes, "_setup_libreoffice_macro", return_value=True), \\
                     mock.patch.object(accept_changes.subprocess, "run",
                                       side_effect=subprocess.TimeoutExpired("soffice", 30)):
                    print(accept_changes.accept_changes({str(src)!r}, {str(Path(tmp) / "out.docx")!r})[1])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.startswith("Error:"), result.stdout)

    def test_docx_comment_creates_missing_document_rels(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "word").mkdir()
            result = run_in(SKILLS / "docx/scripts", f"""
                from pathlib import Path
                from comment import _ensure_comment_relationships
                _ensure_comment_relationships(Path({tmp!r}))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            rels = (Path(tmp) / "word/_rels/document.xml.rels").read_text()
            self.assertIn('Target="comments.xml"', rels)
            self.assertIn('Id="rId1"', rels)


    def test_docx_accept_changes_uses_private_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.docx"
            src.write_bytes(b"x")
            result = run_in(SKILLS / "docx/scripts", f"""
                import os, stat, subprocess
                from pathlib import Path
                from unittest import mock
                import accept_changes
                seen = {{}}
                def fake_run(cmd, **kw):
                    profile = next(a for a in cmd if a.startswith("-env:UserInstallation=")).split("=", 1)[1]
                    path = Path(profile.removeprefix("file://"))
                    path.joinpath("user/basic/Standard").mkdir(parents=True, exist_ok=True)
                    macro = path / "user/basic/Standard/Module1.xba"
                    seen.update(path=str(path), mode=stat.S_IMODE(os.stat(path).st_mode),
                                macro=macro.read_text() if macro.exists() else "")
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                with mock.patch.object(accept_changes.subprocess, "run", side_effect=fake_run):
                    msg = accept_changes.accept_changes({str(src)!r}, {str(Path(tmp) / "out.docx")!r})[1]
                print(msg.startswith("Successfully"), seen["path"] != "/tmp/libreoffice_docx_profile",
                      oct(seen["mode"]), "AcceptAllTrackedChanges" in seen["macro"], Path(seen["path"]).exists())
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split(), ["True", "True", "0o700", "True", "False"])

    def test_soffice_shim_never_loads_planted_tmp_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            planted = Path(tmp) / "lo_socket_shim.so"
            planted.write_bytes(b"attacker")
            result = run_in(SKILLS / "docx/scripts", f"""
                import os, stat, subprocess, tempfile
                from pathlib import Path
                from unittest import mock
                tempfile.tempdir = {tmp!r}
                from office import soffice
                def fake_gcc(cmd, **kw):
                    Path(cmd[cmd.index("-o") + 1]).write_bytes(b"built")
                    return subprocess.CompletedProcess(cmd, 0)
                with mock.patch.object(soffice, "_needs_shim", return_value=True), \\
                     mock.patch.object(soffice.subprocess, "run", side_effect=fake_gcc):
                    shim = Path(soffice.get_soffice_env()["LD_PRELOAD"])
                print(shim != Path({str(planted)!r}), shim.read_bytes() == b"built",
                      oct(stat.S_IMODE(os.stat(shim.parent).st_mode)))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split(), ["True", "True", "0o700"])


class McpEvaluationTests(unittest.TestCase):
    def test_agent_loop_answers_every_tool_use(self):
        result = run_in(SKILLS / "mcp-builder/scripts", """
            import asyncio, sys, types
            sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=object)
            sys.modules["connections"] = types.SimpleNamespace(create_connection=None)
            import evaluation

            Block = lambda **kw: types.SimpleNamespace(**kw)
            replies = [
                Block(stop_reason="tool_use", content=[
                    Block(type="tool_use", id="one", name="a", input={}),
                    Block(type="tool_use", id="two", name="b", input={})]),
                Block(stop_reason="end_turn", content=[Block(type="text", text="<response>ok</response>")]),
            ]
            sent = []
            def create(**kw):
                sent.append([dict(m) for m in kw["messages"]])
                return replies[len(sent) - 1]
            class Conn:
                async def call_tool(self, name, args):
                    return name
            client = types.SimpleNamespace(messages=types.SimpleNamespace(create=create))
            asyncio.run(evaluation.agent_loop(client, "m", "q", [], Conn()))
            print(sorted(r["tool_use_id"] for r in sent[1][-1]["content"]))
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "['one', 'two']")


@unittest.skipIf(sys.platform == "win32", "grupo de processos POSIX")
class WithServerTests(unittest.TestCase):
    def test_server_child_is_stopped(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        # "true;" força o shell a criar um processo filho em vez de executar o servidor no lugar dele.
        server = f"true; {sys.executable} -m http.server {port} --bind 127.0.0.1"
        result = subprocess.run([sys.executable, str(SKILLS / "webapp-testing/scripts/with_server.py"),
                                 "--server", server, "--port", str(port), "--", sys.executable, "-c", "pass"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=1).close()


if __name__ == "__main__":
    unittest.main()
