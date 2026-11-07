"""Regressões das correções locais nas skills de anthropics/skills (ver .agents/anthropic-skills/SOURCE.md)."""
import importlib.util
import shutil
import re
import json
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

    def test_agent_loop_serializes_mcp_content_models(self):
        result = run_in(SKILLS / "mcp-builder/scripts", """
            import asyncio, json, sys, types
            sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=object)
            sys.modules["connections"] = types.SimpleNamespace(create_connection=None)
            import evaluation

            class TextContent:  # imita o modelo pydantic do SDK MCP
                def model_dump(self, mode="python"):
                    return {"type": "text", "text": "ok"}
            Block = lambda **kw: types.SimpleNamespace(**kw)
            replies = [Block(stop_reason="tool_use", content=[Block(type="tool_use", id="one", name="a", input={})]),
                       Block(stop_reason="end_turn", content=[Block(type="text", text="done")])]
            sent = []
            def create(**kw):
                sent.append([dict(m) for m in kw["messages"]])
                return replies[len(sent) - 1]
            class Conn:
                async def call_tool(self, name, args):
                    return [TextContent()]
            client = types.SimpleNamespace(messages=types.SimpleNamespace(create=create))
            asyncio.run(evaluation.agent_loop(client, "m", "q", [], Conn()))
            print(json.loads(sent[1][-1]["content"][0]["content"])[0]["text"])
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "ok")


class SkillCreatorTests(unittest.TestCase):
    def test_viewer_data_cannot_close_script_element(self):
        result = run_in(SKILLS / "skill-creator/eval-viewer", """
            from generate_review import generate_html
            html = generate_html([{"id": "r", "outputs": "<p>x</p></script><script>alert(1)</script>"}], "s")
            start = html.index("const EMBEDDED_DATA = ")
            line = html[start:html.index("\\n", start)]
            print("</script>" in line.lower(), "\\\\u003c/script" in line)
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["False", "True"])

    def test_run_eval_failed_runs_never_pass(self):
        result = run_in(SKILLS / "skill-creator", """
            import concurrent.futures
            from pathlib import Path
            from unittest import mock
            from scripts import run_eval
            def boom(*a, **k):
                raise FileNotFoundError("claude")
            with mock.patch.object(run_eval, "ProcessPoolExecutor", concurrent.futures.ThreadPoolExecutor), \\
                 mock.patch.object(run_eval, "run_single_query", boom):
                out = run_eval.run_eval([{"query": "q", "should_trigger": False}], "s", "d", 1, 1, Path("."), runs_per_query=3)
            r = out["results"][0]
            print(r["pass"], r["errors"], r["runs"], out["summary"]["passed"])
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["False", "3", "0", "0"])

    def test_run_single_query_parses_output_left_at_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_in(SKILLS / "skill-creator", f"""
                import io, json, uuid
                from unittest import mock
                from scripts import run_eval
                event = {{"type": "assistant", "message": {{"content": [
                    {{"type": "tool_use", "name": "Skill", "input": {{"skill": "demo-skill-abcdef12"}}}}]}}}}
                class Done:  # processo que já terminou, com a última linha ainda no pipe
                    stdout = io.BytesIO(json.dumps(event).encode())
                    def poll(self):
                        return 0
                with mock.patch.object(run_eval.uuid, "uuid4", return_value=uuid.UUID("abcdef12" + "0" * 24)), \\
                     mock.patch.object(run_eval.subprocess, "Popen", return_value=Done()):
                    print(run_eval.run_single_query("q", "demo", "d", 5, {tmp!r}))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "True")

    def test_benchmark_reads_real_tokens_when_grading_has_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "eval-1/with_skill/run-1"
            run.mkdir(parents=True)
            (run / "grading.json").write_text(json.dumps({
                "summary": {"pass_rate": 1.0, "passed": 1, "failed": 0, "total": 1},
                "timing": {"total_duration_seconds": 10},
                "execution_metrics": {"output_chars": 1200}}))
            (run / "timing.json").write_text(json.dumps({"total_duration_seconds": 99, "total_tokens": 84852}))
            result = run_in(SKILLS / "skill-creator", f"""
                from pathlib import Path
                from scripts.aggregate_benchmark import load_run_results
                r = load_run_results(Path({tmp!r}))["with_skill"][0]
                print(r["tokens"], r["time_seconds"])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split(), ["84852", "10"])

    def test_viewer_sorts_runs_without_eval_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, meta in (("eval-a", {"eval_id": 1}), ("eval-b", None)):
                run = Path(tmp) / name
                (run / "outputs").mkdir(parents=True)
                (run / "outputs/out.txt").write_text("x")
                if meta:
                    (run / "eval_metadata.json").write_text(json.dumps(meta))
            result = run_in(SKILLS / "skill-creator/eval-viewer", f"""
                from pathlib import Path
                from generate_review import find_runs
                print([r.get("eval_id") for r in find_runs(Path({tmp!r}))])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "[1, None]")


    @unittest.skipUnless(shutil.which("node"), "node não disponível")
    def test_viewer_escape_html_is_safe_in_attributes(self):
        html = (SKILLS / "skill-creator/eval-viewer/viewer.html").read_text()
        body = re.search(r"function escapeHtml\(text\) \{.*?\n    \}", html, re.S).group(0)
        # Stub com a serialização de innerHTML do navegador para texto: escapa só &, < e >.
        script = textwrap.dedent("""
            const document = {createElement() { return {
              set textContent(t) { this.t = String(t); },
              get innerHTML() { return this.t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
            }; }};
        """) + body + '\nprocess.stdout.write(escapeHtml(\'x" onmouseover="alert(1)\'));'
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('"', result.stdout)
        self.assertEqual(result.stdout, "x&quot; onmouseover=&quot;alert(1)")


@unittest.skipUnless(importlib.util.find_spec("openpyxl") and importlib.util.find_spec("pypdf"),
                     "openpyxl/pypdf não instalados")
class XlsxPdfTests(unittest.TestCase):
    def test_xlsx_recalc_counts_only_real_error_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp) / "book.xlsx"
            result = run_in(SKILLS / "xlsx/scripts", f"""
                import os, subprocess
                from pathlib import Path
                from unittest import mock
                from openpyxl import Workbook
                import recalc
                wb = Workbook()
                wb.active["A1"] = "Como corrigir #VALUE!"
                wb.active["A2"] = "#DIV/0!"
                wb.save({str(book)!r})
                def fake_run(cmd, **kw):
                    st = os.stat({str(book)!r})
                    os.utime({str(book)!r}, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                with mock.patch.object(recalc, "setup_libreoffice_macro", return_value=("file:///p", None)), \\
                     mock.patch.object(recalc.subprocess, "run", side_effect=fake_run):
                    out = recalc._recalc_with_profile({str(book)!r}, {str(book)!r}, 30, Path({tmp!r}))
                print(out["total_errors"], sorted(out["error_summary"]))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "1 ['#DIV/0!']")

    def test_pdf_choice_options_accept_plain_strings(self):
        result = run_in(SKILLS / "pdf/scripts", """
            from extract_form_field_info import make_field_dict
            d = make_field_dict({"/FT": "/Ch", "/_States_": ["Red", ["g", "Green"], "M"]}, "f")
            print(d["choice_options"])
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(),
                         "[{'value': 'Red', 'text': 'Red'}, {'value': 'g', 'text': 'Green'}, {'value': 'M', 'text': 'M'}]")


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

    def test_chatty_server_does_not_block_on_full_pipe(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        # Escreve 1 MB antes de abrir a porta: com PIPE não lido, o servidor travava.
        server = (f"{sys.executable} -c \"import sys; sys.stdout.write('x' * 1048576); sys.stdout.flush()\"; "
                  f"{sys.executable} -m http.server {port} --bind 127.0.0.1")
        result = subprocess.run([sys.executable, str(SKILLS / "webapp-testing/scripts/with_server.py"),
                                 "--server", server, "--port", str(port), "--timeout", "15",
                                 "--", sys.executable, "-c", "pass"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-500:])


if __name__ == "__main__":
    unittest.main()
