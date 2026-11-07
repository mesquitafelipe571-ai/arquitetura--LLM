"""Regressões das correções locais nas skills de anthropics/skills (ver .agents/anthropic-skills/SOURCE.md)."""
from html.parser import HTMLParser
import importlib.util
import shutil
import re
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
import xml.etree.ElementTree as ET
import zipfile

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

    def test_pptx_thumbnail_reads_slides_listed_with_other_prefix(self):
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        with tempfile.TemporaryDirectory() as tmp:
            pptx = Path(tmp) / "deck.pptx"
            with zipfile.ZipFile(pptx, "w") as zf:
                zf.writestr("ppt/presentation.xml",
                            '<x:presentation xmlns:x="http://schemas.openxmlformats.org/presentationml/2006/main"'
                            f' xmlns:rel="{rel_ns}"><x:sldIdLst><x:sldId id="256" rel:id="rId2"/>'
                            '</x:sldIdLst></x:presentation>')
                zf.writestr("ppt/_rels/presentation.xml.rels",
                            '<pr:Relationships xmlns:pr="http://schemas.openxmlformats.org/package/2006/relationships">'
                            f'<pr:Relationship Id="rId2" Type="{rel_ns}/slide" Target="slides/slide1.xml"/>'
                            '</pr:Relationships>')
                zf.writestr("ppt/slides/slide1.xml", "<x/>")
            result = run_in(SKILLS / "pptx/scripts", f"""
                from pathlib import Path
                from thumbnail import get_slide_info
                print(get_slide_info(Path({str(pptx)!r})))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "[{'name': 'slide1.xml', 'hidden': False}]")

    def test_pptx_clean_keeps_media_referenced_with_prefixed_rels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for d in ("ppt/_rels", "ppt/slides/_rels", "ppt/media"):
                (root / d).mkdir(parents=True)
            rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            (root / "ppt/presentation.xml").write_text(
                '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
                f' xmlns:r="{rel_type}"><p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst>'
                '</p:presentation>')
            (root / "ppt/_rels/presentation.xml.rels").write_text(
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rId2" Type="{rel_type}/slide" Target="slides/slide1.xml"/></Relationships>')
            (root / "ppt/slides/slide1.xml").write_text("<x/>")
            (root / "ppt/slides/_rels/slide1.xml.rels").write_text(
                '<r:Relationships xmlns:r="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<r:Relationship Id="rId1" Type="{rel_type}/image" Target="../media/image1.png"/>'
                '</r:Relationships>')
            (root / "ppt/media/image1.png").write_bytes(b"png")
            result = run_in(SKILLS / "pptx/scripts", f"""
                from pathlib import Path
                from clean import clean_unused_files
                print(clean_unused_files(Path({tmp!r})))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "[]")
            self.assertTrue((root / "ppt/media/image1.png").exists())

    def test_pptx_add_slide_registers_in_prefixed_rels_and_types(self):
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ppt/_rels").mkdir(parents=True)
            (root / "ppt/presentation.xml").write_text(
                '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
                f' xmlns:r="{rel_ns}"><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst></p:presentation>')
            (root / "ppt/_rels/presentation.xml.rels").write_text(
                '<pkg:Relationships xmlns:pkg="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<pkg:Relationship Id="rId1" Type="{rel_ns}/slide" Target="slides/slide1.xml"/></pkg:Relationships>')
            (root / "[Content_Types].xml").write_text(
                '<ct:Types xmlns:ct="http://schemas.openxmlformats.org/package/2006/content-types"></ct:Types>')
            result = run_in(SKILLS / "pptx/scripts", f"""
                from pathlib import Path
                from add_slide import _add_to_content_types, _add_to_presentation_rels
                _add_to_content_types(Path({tmp!r}), "slide2.xml")
                print(_add_to_presentation_rels(Path({tmp!r}), "slide2.xml"))
                print(_add_to_presentation_rels(Path({tmp!r}), "slide1.xml"))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split(), ["rId2", "rId1"])
            ns = {"pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
                  "ct": "http://schemas.openxmlformats.org/package/2006/content-types"}
            rels = ET.parse(root / "ppt/_rels/presentation.xml.rels").getroot()
            self.assertEqual([r.get("Target") for r in rels.findall("pkg:Relationship", ns)],
                             ["slides/slide1.xml", "slides/slide2.xml"])
            types = ET.parse(root / "[Content_Types].xml").getroot()
            self.assertEqual([o.get("PartName") for o in types.findall("ct:Override", ns)],
                             ["/ppt/slides/slide2.xml"])

    def test_pptx_add_slide_reads_single_quoted_ids(self):
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ppt/_rels").mkdir(parents=True)
            (root / "ppt/presentation.xml").write_text(
                "<p:presentation xmlns:p='http://schemas.openxmlformats.org/presentationml/2006/main'"
                f" xmlns:r='{rel_ns}'><p:sldIdLst><p:sldId id='300' r:id='rId1'/></p:sldIdLst></p:presentation>")
            (root / "ppt/_rels/presentation.xml.rels").write_text(
                "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
                f"<Relationship Id='rId1' Type='{rel_ns}/slide' Target='slides/slide1.xml'/></Relationships>")
            result = run_in(SKILLS / "pptx/scripts", f"""
                from pathlib import Path
                from add_slide import _add_to_presentation_rels, _get_next_slide_id
                print(_add_to_presentation_rels(Path({tmp!r}), "slide1.xml"))
                print(_add_to_presentation_rels(Path({tmp!r}), "slide2.xml"))
                print(_get_next_slide_id(Path({tmp!r})))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split(), ["rId1", "rId2", "301"])

    def test_pptx_duplicate_slide_drops_prefixed_notes_relationship(self):
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ppt/_rels").mkdir(parents=True)
            (root / "ppt/slides/_rels").mkdir(parents=True)
            (root / "ppt/presentation.xml").write_text(
                '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
                f' xmlns:r="{rel_ns}"><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst></p:presentation>')
            (root / "ppt/_rels/presentation.xml.rels").write_text(
                f'<Relationships xmlns="{pkg}"><Relationship Id="rId1" Type="{rel_ns}/slide"'
                ' Target="slides/slide1.xml"/></Relationships>')
            (root / "[Content_Types].xml").write_text(
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
            (root / "ppt/slides/slide1.xml").write_text("<p:sld/>")
            (root / "ppt/slides/_rels/slide1.xml.rels").write_text(
                f'<pkg:Relationships xmlns:pkg="{pkg}">'
                f'<pkg:Relationship Id="rId1" Type="{rel_ns}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
                f'<pkg:Relationship Id="rId2" Type="{rel_ns}/notesSlide" Target="../notesSlides/notesSlide1.xml"/>'
                '</pkg:Relationships>')
            result = run_in(SKILLS / "pptx/scripts", f"""
                from pathlib import Path
                from add_slide import duplicate_slide
                print(duplicate_slide(Path({tmp!r}), "slide1.xml"))
            """)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(result.stdout.splitlines()[-1], "slide2.xml")
            rels = ET.parse(root / "ppt/slides/_rels/slide2.xml.rels").getroot()
            self.assertEqual([r.get("Type").rsplit("/", 1)[1] for r in rels], ["slideLayout"])

    def test_docx_comment_declares_namespaces_used_by_new_comment(self):
        with tempfile.TemporaryDirectory() as tmp:
            comments = Path(tmp) / "comments.xml"
            comments.write_text('<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                                '<w:comment w:id="0"/></w:comments>')
            result = run_in(SKILLS / "docx/scripts", f"""
                from pathlib import Path
                from comment import _append_xml
                _append_xml(Path({str(comments)!r}), "w:comments",
                            '<w:comment w:id="1"><w:p w14:paraId="0000ABCD"/></w:comment>')
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            root = ET.parse(comments).getroot()  # falha com "unbound prefix" sem a declaração
            w14 = "{http://schemas.microsoft.com/office/word/2010/wordml}paraId"
            self.assertEqual([p.get(w14) for p in root.iter() if p.get(w14)], ["0000ABCD"])

    def test_docx_comment_parts_keep_prefixed_namespaces(self):
        pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
        ct = "http://schemas.openxmlformats.org/package/2006/content-types"
        img = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "word/_rels").mkdir(parents=True)
            (root / "word/_rels/document.xml.rels").write_text(
                f'<pkg:Relationships xmlns:pkg="{pkg}"><pkg:Relationship Id="rId1" Type="{img}"'
                ' Target="media/image1.png"/></pkg:Relationships>')
            (root / "[Content_Types].xml").write_text(
                f'<ct:Types xmlns:ct="{ct}"><ct:Override PartName="/word/comments.xml" ContentType="x"/></ct:Types>')
            (root / "word/comments.xml").write_text(
                '<x:comments xmlns:x="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<x:comment x:id="4"/></x:comments>')
            result = run_in(SKILLS / "docx/scripts", f"""
                from pathlib import Path
                from comment import _ensure_comment_content_types, _ensure_comment_relationships, _next_comment_id
                _ensure_comment_relationships(Path({tmp!r}))
                _ensure_comment_content_types(Path({tmp!r}))
                print(_next_comment_id(Path({tmp!r}) / "word/comments.xml"))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "5")
            rels = ET.parse(root / "word/_rels/document.xml.rels").getroot()
            ids = [r.get("Id") for r in rels.findall(f"{{{pkg}}}Relationship")]
            self.assertEqual(len(ids), 5)
            self.assertEqual(len(set(ids)), 5)  # nenhum rId reutilizado
            self.assertEqual(len(rels), 5)  # todos os filhos no namespace OPC
            types = ET.parse(root / "[Content_Types].xml").getroot()
            parts = [o.get("PartName") for o in types.findall(f"{{{ct}}}Override")]
            self.assertEqual(len(types), 4)
            self.assertEqual(parts.count("/word/comments.xml"), 1)

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


    def test_cli_examples_keep_eval_file_after_repeatable_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "eval.xml").write_text("<evaluation/>")
            result = run_in(SKILLS / "mcp-builder/scripts", f"""
                import asyncio, os, sys, types
                os.chdir({tmp!r})
                def fake_connection(**kw):
                    print(sorted((k, v) for k, v in kw.items() if v))
                    raise SystemExit(0)
                sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=object)
                sys.modules["connections"] = types.SimpleNamespace(create_connection=fake_connection)
                import evaluation
                sys.argv = ["evaluation.py", "-t", "stdio", "-c", "python", "-a", "my_server.py",
                            "-e", "A=1", "-e", "B=2", "eval.xml"]
                asyncio.run(evaluation.main())
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("('args', ['my_server.py'])", result.stdout)
            self.assertIn("('env', {'A': '1', 'B': '2'})", result.stdout)

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

    def test_run_single_query_keeps_reading_after_other_tools(self):
        # Read de outro arquivo antes do Skill, nos dois formatos de saída (mensagem completa e streaming).
        read = {"type": "tool_use", "name": "Read", "input": {"file_path": "/tmp/context.md"}}
        skill = {"type": "tool_use", "name": "Skill", "input": {"skill": "demo-skill-abcdef12"}}
        def block(cb):
            return {"type": "stream_event", "event": {"type": "content_block_start", "content_block": cb}}
        def delta(text):
            return {"type": "stream_event", "event": {"type": "content_block_delta",
                    "delta": {"type": "input_json_delta", "partial_json": text}}}
        stop = {"type": "stream_event", "event": {"type": "content_block_stop"}}
        streams = {
            "assistant": [{"type": "assistant", "message": {"content": [read, skill]}}],
            "stream": [block({"type": "tool_use", "name": "Grep"}), stop,
                       block({"type": "tool_use", "name": "Read"}), delta('{"file_path": "/tmp/context.md"}'), stop,
                       {"type": "stream_event", "event": {"type": "message_stop"}},
                       block({"type": "tool_use", "name": "Skill"}), delta('{"skill": "demo-skill-abcdef12"}'), stop],
        }
        for name, events in streams.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                payload = "\n".join(json.dumps(e) for e in events)
                result = run_in(SKILLS / "skill-creator", f"""
                    import io, uuid
                    from unittest import mock
                    from scripts import run_eval
                    class Done:
                        stdout = io.BytesIO({payload.encode()!r})
                        def poll(self):
                            return 0
                    with mock.patch.object(run_eval.uuid, "uuid4", return_value=uuid.UUID("abcdef12" + "0" * 24)), \\
                         mock.patch.object(run_eval.subprocess, "Popen", return_value=Done()):
                        print(run_eval.run_single_query("q", "demo", "d", 5, {tmp!r}))
                """)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "True")

    def test_package_skill_skips_its_own_output_inside_the_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "my-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text("---\nname: my-skill\ndescription: x\n---\n")
            result = run_in(SKILLS / "skill-creator", f"""
                import sys, types, zipfile
                sys.modules["scripts.quick_validate"] = types.SimpleNamespace(validate_skill=lambda p: (True, "ok"))
                from scripts.package_skill import package_skill
                out = package_skill({str(skill)!r}, {str(skill / "dist")!r})
                print(sorted(zipfile.ZipFile(out).namelist()))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip().splitlines()[-1], "['my-skill/SKILL.md']")

    def test_viewer_reads_eval_metadata_above_numbered_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "eval-3/with_skill/run-1"
            (run / "outputs").mkdir(parents=True)
            (Path(tmp) / "eval-3/eval_metadata.json").write_text(json.dumps({"eval_id": 3, "prompt": "Tarefa"}))
            result = run_in(SKILLS / "skill-creator/eval-viewer", f"""
                from pathlib import Path
                from generate_review import find_runs
                print([(r.get("eval_id"), r.get("prompt")) for r in find_runs(Path({tmp!r}))])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "[(3, 'Tarefa')]")

    def test_run_single_query_accepts_copies_from_same_run_only(self):
        # Workers paralelos compartilham .claude/commands: a cópia de outro worker da mesma execução vale.
        for selected, expected in (("demo-skill-feedc0de-11111111", "True"), ("demo-skill-0badf00d-22222222", "False")):
            with self.subTest(selected), tempfile.TemporaryDirectory() as tmp:
                event = {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": selected}}]}}
                result = run_in(SKILLS / "skill-creator", f"""
                    import io, json
                    from unittest import mock
                    from scripts import run_eval
                    class Done:
                        stdout = io.BytesIO({(json.dumps(event) + chr(10) + json.dumps({"type": "result"})).encode()!r})
                        def poll(self):
                            return 0
                    with mock.patch.object(run_eval.subprocess, "Popen", return_value=Done()):
                        print(run_eval.run_single_query("q", "demo", "d", 5, {tmp!r}, run_tag="feedc0de"))
                """)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)

    @unittest.skipUnless(shutil.which("node"), "node não disponível")
    def test_eval_review_recipe_keeps_script_intact(self):
        skill_md = (SKILLS / "skill-creator/SKILL.md").read_text()
        recipe = re.search(r"```python\n(\s*import html, json\n.*?)```", skill_md, re.S).group(1)
        items = [{"query": 'gere <script>console.log("hi")</script> em HTML', "should_trigger": True}]
        scope = {"template": (SKILLS / "skill-creator/assets/eval_review.html").read_text(),
                 "eval_items": items, "skill_name": "x</title><b>", "skill_description": "<img src=x onerror=1>"}
        exec(textwrap.dedent(recipe), scope)
        page = scope["page"]
        self.assertNotIn("<img", page)
        self.assertNotIn("</title><b>", page)
        class FirstScript(HTMLParser):  # como o navegador: o primeiro </script>, em qualquer caixa, encerra o elemento
            text = None
            def handle_starttag(self, tag, attrs):
                self.inside = tag == "script" and self.text is None
            def handle_data(self, data):
                if getattr(self, "inside", False):
                    self.text, self.inside = data, False
        parser = FirstScript()
        parser.feed(page)
        script = parser.text
        data = re.search(r"const EVAL_DATA = (.*?);\n", script).group(1)
        result = subprocess.run(["node", "-e", f"process.stdout.write(JSON.stringify({data}))"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), items)

    def test_package_skill_ignores_links_in_excluded_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "my-skill"
            (skill / "node_modules/demo-dep").mkdir(parents=True)
            (skill / "SKILL.md").write_text("---\nname: my-skill\ndescription: x\n---\n")
            (skill / "node_modules/demo-dep/bin").symlink_to(sys.executable)
            result = run_in(SKILLS / "skill-creator", f"""
                import sys, types, zipfile
                sys.modules["scripts.quick_validate"] = types.SimpleNamespace(validate_skill=lambda p: (True, "ok"))
                from scripts.package_skill import package_skill
                out = package_skill({str(skill)!r}, {str(Path(tmp) / "dist")!r})
                print(sorted(zipfile.ZipFile(out).namelist()))
            """)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(result.stdout.strip().splitlines()[-1], "['my-skill/SKILL.md']")

    @unittest.skipUnless(shutil.which("node"), "node não disponível")
    def test_viewer_final_submit_is_not_overwritten_by_pending_autosave(self):
        html = (SKILLS / "skill-creator/eval-viewer/viewer.html").read_text()
        state = re.search(r"// ---- State ----\n(.*?)\n\n", html, re.S).group(1)
        funcs = [re.search(rf"(?:async )?function {name}\(\) \{{.*?\n    \}}", html, re.S).group(0)
                 for name in ("init", "saveCurrentFeedback", "showDoneDialog")]
        script = textwrap.dedent("""
            const EMBEDDED_DATA = {skill_name: "s", runs: [{id: "r1"}, {id: "r2"}]};
            const location = {search: "?token=t"};
            const posts = [];
            async function fetch(url, opts) {
              if (opts && opts.method === "POST") posts.push(JSON.parse(opts.body).status);
              await new Promise(r => setTimeout(r, 50));  // uma requisição em andamento
              return {json: async () => ({})};
            }
            const els = {};
            const document = {getElementById(id) {
              return els[id] || (els[id] = {value: "", handlers: {}, classList: {add() {}, remove() {}},
                addEventListener(ev, fn) { this.handlers[ev] = fn; }, set textContent(t) {}});
            }};
            function showRun() {}
        """) + state + "\n" + "\n".join(funcs) + textwrap.dedent("""
            init().then(() => {
              const box = document.getElementById("feedback");
              box.value = "ok";
              box.handlers.input();       // agenda o salvamento automático (800 ms)
              saveCurrentFeedback();       // e há um salvamento em andamento
              showDoneDialog();            // o usuário conclui antes dos 800 ms
              setTimeout(() => process.stdout.write(JSON.stringify(posts)), 1200);
            });
        """)
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[-1], "complete")

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

    def test_benchmark_reads_documented_layout_without_run_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            for config, rate in (("with_skill", 1.0), ("without_skill", 0.5)):
                d = Path(tmp) / "eval-0" / config
                (d / "outputs").mkdir(parents=True)
                (d / "grading.json").write_text(json.dumps({"summary": {"pass_rate": rate}}))
            result = run_in(SKILLS / "skill-creator", f"""
                from pathlib import Path
                from scripts.aggregate_benchmark import load_run_results
                r = load_run_results(Path({tmp!r}))
                print(sorted((k, [(x["run_number"], x["pass_rate"]) for x in v]) for k, v in r.items()))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(),
                             "[('with_skill', [(1, 1.0)]), ('without_skill', [(1, 0.5)])]")

    def test_package_skill_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp) / "credentials.env"
            secret.write_text("TOKEN=segredo")
            skill = Path(tmp) / "my-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text("---\nname: my-skill\ndescription: x\n---\n")
            (skill / "notes.txt").symlink_to(secret)
            out = Path(tmp) / "dist"
            result = run_in(SKILLS / "skill-creator", f"""
                import sys, types
                sys.modules["scripts.quick_validate"] = types.SimpleNamespace(validate_skill=lambda p: (True, "ok"))
                from scripts.package_skill import package_skill
                print(package_skill({str(skill)!r}, {str(out)!r}))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("symbolic link not allowed", result.stdout)
            self.assertEqual(result.stdout.strip().splitlines()[-1], "None")
            self.assertFalse((out / "my-skill.skill").exists())

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


    def test_viewer_server_requires_per_run_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_in(SKILLS / "skill-creator/eval-viewer", f"""
                import json, threading, urllib.error, urllib.request
                from functools import partial
                from http.server import HTTPServer
                from pathlib import Path
                from generate_review import ReviewHandler
                fb = Path({tmp!r}) / "feedback.json"
                handler = partial(ReviewHandler, Path({tmp!r}), "s", fb, {{}}, None, "segredo")
                server = HTTPServer(("127.0.0.1", 0), handler)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                base = "http://127.0.0.1:%d" % server.server_address[1]
                def status(url, body=None):
                    try:
                        return urllib.request.urlopen(urllib.request.Request(url, data=body)).status
                    except urllib.error.HTTPError as e:
                        return e.code
                body = json.dumps({{"reviews": []}}).encode()
                print(status(base + "/"), status(base + "/api/feedback"),
                      status(base + "/api/feedback", body), fb.exists(),
                      status(base + "/api/feedback?token=errado"),
                      status(base + "/api/feedback?token=segredo", body), fb.exists())
                server.shutdown()
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split(), ["403", "403", "403", "False", "403", "200", "True"])

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

    def test_viewer_loads_current_feedback_with_previous_iteration(self):
        html = (SKILLS / "skill-creator/eval-viewer/viewer.html").read_text()
        body = re.search(r"async function init\(\) \{.*?\n    \}", html, re.S).group(0)
        script = textwrap.dedent("""
            let feedbackMap = {};
            const EMBEDDED_DATA = {skill_name: "s", previous_outputs: {"r1": [{}]}, previous_feedback: {"r1": "velho"}};
            const location = {search: "?token=t"};
            let fetched = null;
            async function fetch(url) { fetched = url; return {json: async () => ({reviews: [{run_id: "r1", feedback: "atual"}]})}; }
            const el = {addEventListener() {}, set textContent(t) {}};
            const document = {getElementById() { return el; }};
            function showRun() {}
        """) + body + "\ninit().then(() => process.stdout.write(JSON.stringify([fetched, feedbackMap])));"
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["/api/feedback?token=t", {"r1": "atual"}])

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

    def test_pdf_keeps_text_field_with_separate_widget(self):
        result = run_in(SKILLS / "pdf/scripts", """
            from extract_form_field_info import get_field_info
            class Obj(dict):
                def get_object(self):
                    return self
            field = Obj({"/FT": "/Tx", "/T": "name"})
            widget = Obj({"/Parent": field, "/Rect": [0, 0, 10, 10]})
            field["/Kids"] = [widget]
            class Reader:
                pages = [{"/Annots": [widget]}]
                def get_fields(self):
                    return {"name": field}
            print([f["field_id"] for f in get_field_info(Reader())])
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "['name']")

    def test_pdf_checkbox_with_separate_widget_stays_checkbox(self):
        result = run_in(SKILLS / "pdf/scripts", """
            from extract_form_field_info import get_field_info
            class Obj(dict):
                def get_object(self):
                    return self
            field = Obj({"/FT": "/Btn", "/T": "agree", "/Ff": 0})
            widget = Obj({"/Parent": field, "/Rect": [0, 0, 10, 10],
                          "/AP": {"/N": {"/Yes": None, "/Off": None}}})
            field["/Kids"] = [widget]
            class Reader:
                pages = [{"/Annots": [widget]}]
                def get_fields(self):
                    return {"agree": field}
            f = get_field_info(Reader())[0]
            print(f["type"], f["checked_value"], f["unchecked_value"])
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "checkbox /Yes /Off")

    def test_pdf_bounding_box_height_uses_points_for_image_coordinates(self):
        fields = json.dumps({
            "pages": [{"page_number": 1, "image_width": 1275, "image_height": 1650}],
            "form_fields": [{"page_number": 1, "description": "nome",
                             "label_bounding_box": [0, 0, 50, 12], "entry_bounding_box": [60, 0, 300, 12],
                             "entry_text": {"text": "x", "font_size": 10}}]})
        result = run_in(SKILLS / "pdf/scripts", f"""
            import io
            from check_bounding_boxes import get_bounding_box_messages
            print(get_bounding_box_messages(io.StringIO({fields!r}), {{1: 792.0}})[-1].split(":")[0])
            print(get_bounding_box_messages(io.StringIO({fields!r}))[-2].split(":")[0])
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["FAILURE", "WARNING"])

    def test_pdf_convert_creates_missing_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "novo/images_dir"
            result = run_in(SKILLS / "pdf/scripts", f"""
                import sys, types
                from PIL import Image
                sys.modules["pdf2image"] = types.SimpleNamespace(
                    convert_from_path=lambda path, dpi: [Image.new("RGB", (10, 10))])
                from convert_pdf_to_images import convert
                convert("x.pdf", {str(out)!r})
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((out / "page_1.png").exists())

    def test_pdf_choice_options_accept_plain_strings(self):
        result = run_in(SKILLS / "pdf/scripts", """
            from extract_form_field_info import make_field_dict
            d = make_field_dict({"/FT": "/Ch", "/_States_": ["Red", ["g", "Green"], "M"]}, "f")
            print(d["choice_options"])
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(),
                         "[{'value': 'Red', 'text': 'Red'}, {'value': 'g', 'text': 'Green'}, {'value': 'M', 'text': 'M'}]")



@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("PIL"),
                     "numpy/Pillow não instalados")
class GifBuilderTests(unittest.TestCase):
    def test_emoji_frame_reduction_keeps_animation_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_in(SKILLS / "slack-gif-creator", f"""
                import sys, types
                seen = {{}}
                def imwrite(path, frames, duration, loop):  # imageio substituído: só registra
                    seen["duration"] = duration
                    open(path, "wb").write(b"gif")
                sys.modules["imageio"] = types.ModuleType("imageio")
                sys.modules["imageio.v3"] = types.SimpleNamespace(imwrite=imwrite)
                import numpy as np
                from core.gif_builder import GIFBuilder
                b = GIFBuilder(128, 128, fps=12)
                for i in range(24):
                    b.add_frame(np.full((128, 128, 3), i * 10, dtype=np.uint8))
                info = b.save({str(Path(tmp) / "e.gif")!r}, optimize_for_emoji=True)
                print(round(seen["duration"] * info["frame_count"]), info["duration_seconds"])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines()[-1].split(), ["2000", "2.0"])

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

    def test_child_ignoring_sigterm_is_killed(self):
        # O shell sai com o SIGTERM, mas o filho o ignora: antes, o SIGKILL nunca chegava ao grupo.
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "child.pid"
            child = (f"{sys.executable} -c \"import os, signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                     f"open({str(pidfile)!r}, 'w').write(str(os.getpid())); time.sleep(60)\"")
            result = run_in(SKILLS / "webapp-testing/scripts", f"""
                import subprocess, time
                from pathlib import Path
                from with_server import stop_server
                proc = subprocess.Popen({(child + " >/dev/null 2>&1 & wait")!r}, shell=True, start_new_session=True)
                while not Path({str(pidfile)!r}).exists():
                    time.sleep(0.05)
                time.sleep(0.2)
                stop_server(proc)
                print(Path({str(pidfile)!r}).read_text())
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            pid = int(result.stdout.strip())
            for _ in range(50):  # o init pode levar um instante para recolher o processo
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
            else:
                os.kill(pid, 9)
                self.fail("o filho que ignora SIGTERM continuou vivo")

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
