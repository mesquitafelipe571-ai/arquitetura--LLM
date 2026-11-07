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
    def test_redlining_counts_tabs_and_breaks(self):
        # Remover <w:tab/> sem rastrear muda o texto visível; com <w:del> a mudança está registrada.
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        doc = f'<w:document xmlns:w="{w}"><w:body><w:p>{{}}</w:p></w:body></w:document>'
        original = '<w:r><w:t>Pay</w:t><w:tab/><w:t>100</w:t></w:r>'
        cases = {
            "untracked": ('<w:r><w:t>Pay100</w:t></w:r>', False),
            "tracked": ('<w:r><w:t>Pay</w:t></w:r><w:del w:author="A"><w:r><w:tab/></w:r></w:del>'
                        '<w:r><w:t>100</w:t></w:r>', True),
            "br": ('<w:r><w:t>Pay</w:t><w:br/><w:t>100</w:t></w:r>', False),
        }
        for skill in ("docx", "pptx", "xlsx"):
            for name, (modified, expected) in cases.items():
                with self.subTest(skill=skill, case=name), tempfile.TemporaryDirectory() as tmp:
                    src = Path(tmp) / "original.docx"
                    with zipfile.ZipFile(src, "w") as z:
                        z.writestr("word/document.xml", doc.format(original))
                    (Path(tmp) / "out/word").mkdir(parents=True)
                    (Path(tmp) / "out/word/document.xml").write_text(doc.format(modified))
                    result = run_in(SKILLS / f"{skill}/scripts/office", f"""
                        from validators.redlining import RedliningValidator
                        print(RedliningValidator({str(Path(tmp) / "out")!r}, {str(src)!r}).validate())
                    """)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip().splitlines()[-1], str(expected))

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

    def test_pptx_clean_refuses_when_presentation_index_is_missing(self):
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ppt/_rels").mkdir(parents=True)
            (root / "ppt/slides").mkdir()
            (root / "ppt/_rels/presentation.xml.rels").write_text(
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rId2" Type="{rel_ns}/slide" Target="slides/slide1.xml"/></Relationships>')
            (root / "ppt/slides/slide1.xml").write_text("<p:sld/>")  # presentation.xml ausente
            result = run_in(SKILLS / "pptx/scripts", f"""
                from pathlib import Path
                from clean import RefusedToClean, clean_unused_files
                try:
                    print(clean_unused_files(Path({tmp!r})))
                except RefusedToClean as e:
                    print("recusado:", e)
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.startswith("recusado:"), result.stdout)
            self.assertTrue((root / "ppt/slides/slide1.xml").exists())

    def test_pptx_clean_refuses_when_listed_slide_has_no_relationship(self):
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ppt/_rels").mkdir(parents=True)
            (root / "ppt/slides").mkdir()
            (root / "ppt/presentation.xml").write_text(
                '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
                f' xmlns:r="{rel_ns}"><p:sldIdLst><p:sldId id="256" r:id="rId1"/><p:sldId id="257" r:id="rId2"/>'
                '</p:sldIdLst></p:presentation>')
            (root / "ppt/_rels/presentation.xml.rels").write_text(
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rId1" Type="{rel_ns}/slide" Target="slides/slide1.xml"/></Relationships>')
            for n in (1, 2):
                (root / f"ppt/slides/slide{n}.xml").write_text("<p:sld/>")
            result = run_in(SKILLS / "pptx/scripts", f"""
                from pathlib import Path
                from clean import RefusedToClean, clean_unused_files
                try:
                    print(clean_unused_files(Path({tmp!r})))
                except RefusedToClean as e:
                    print("recusado:", e)
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.startswith("recusado:"), result.stdout)
            self.assertIn("rId2", result.stdout)
            self.assertTrue((root / "ppt/slides/slide2.xml").exists())

    def test_pptx_thumbnail_refuses_zip_bomb_before_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            pptx = Path(tmp) / "bomb.pptx"
            with zipfile.ZipFile(pptx, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("ppt/presentation.xml", b" " * (32 * 1024 * 1024))  # ~32 KB comprimido
            result = run_in(SKILLS / "pptx/scripts", f"""
                from pathlib import Path
                from thumbnail import get_slide_info
                try:
                    get_slide_info(Path({str(pptx)!r}))
                    print("lido")
                except ValueError as e:
                    print("recusado:", e)
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.startswith("recusado: suspicious compression ratio"), result.stdout)

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

    def test_pptx_duplicate_slide_with_other_presentation_prefixes(self):
        # Mesmo namespace com outros prefixos (deck:, rel:): antes a lista de slides "não existia".
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        pml = "http://schemas.openxmlformats.org/presentationml/2006/main"
        pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ppt/_rels").mkdir(parents=True)
            (root / "ppt/slides/_rels").mkdir(parents=True)
            (root / "ppt/presentation.xml").write_text(
                f'<deck:presentation xmlns:deck="{pml}" xmlns:rel="{rel_ns}">'
                '<deck:sldIdLst><deck:sldId id="256" rel:id="rId1"/></deck:sldIdLst></deck:presentation>')
            (root / "ppt/_rels/presentation.xml.rels").write_text(
                f'<Relationships xmlns="{pkg}"><Relationship Id="rId1" Type="{rel_ns}/slide"'
                ' Target="slides/slide1.xml"/></Relationships>')
            (root / "[Content_Types].xml").write_text(
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
            (root / "ppt/slides/slide1.xml").write_text("<p:sld/>")
            (root / "ppt/slides/_rels/slide1.xml.rels").write_text(
                f'<Relationships xmlns="{pkg}"><Relationship Id="rId1" Type="{rel_ns}/slideLayout"'
                ' Target="../slideLayouts/slideLayout1.xml"/></Relationships>')
            result = run_in(SKILLS / "pptx/scripts", f"""
                from pathlib import Path
                from add_slide import add_slide
                print(add_slide(Path({tmp!r}), "slide1.xml"))
            """)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            ids = ET.parse(root / "ppt/presentation.xml").getroot().find(f"{{{pml}}}sldIdLst")
            self.assertEqual([(e.get("id"), e.get(f"{{{rel_ns}}}id")) for e in ids],
                             [("256", "rId1"), ("257", "rId2")])

    def test_pptx_next_slide_id_reads_spaced_attributes(self):
        # id = "256" (espaços em volta do =) é XML válido; ignorá-lo repetia o id 256.
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "ppt").mkdir()
            (Path(tmp) / "ppt/presentation.xml").write_text(
                '<p:presentation xmlns:p = "http://schemas.openxmlformats.org/presentationml/2006/main"'
                ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<p:sldIdLst><p:sldId id = "256" r:id = "rId1"/></p:sldIdLst></p:presentation>')
            result = run_in(SKILLS / "pptx/scripts", f"""
                from pathlib import Path
                from add_slide import _get_next_slide_id
                print(_get_next_slide_id(Path({tmp!r})))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "257")

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

    def test_docx_merge_runs_keeps_namespaces_declared_on_merged_run(self):
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        a = "http://schemas.openxmlformats.org/drawingml/2006/main"
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "word").mkdir()
            (Path(tmp) / "word/document.xml").write_text(
                f'<w:document xmlns:w="{w}"><w:body><w:p>'
                '<w:r><w:t>texto</w:t></w:r>'
                f'<w:r xmlns:a="{a}"><w:drawing><a:graphic/></w:drawing></w:r>'
                '</w:p></w:body></w:document>')
            result = run_in(SKILLS / "docx/scripts", f"""
                from merge_runs import merge_runs
                print(merge_runs({tmp!r}))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            root = ET.parse(Path(tmp) / "word/document.xml").getroot()  # "unbound prefix" sem a correção
            runs = root.findall(f".//{{{w}}}r")
            self.assertEqual(len(runs), 1)
            self.assertIsNotNone(runs[0].find(f".//{{{a}}}graphic"))

    def test_office_safe_extract_refuses_linked_destination(self):
        # unpacked -> victim (ou uma pasta acima que seja link): a extração escreveria fora do workspace.
        for skill in ("docx", "pptx", "xlsx"):
            with self.subTest(skill), tempfile.TemporaryDirectory() as tmp:
                doc = Path(tmp) / "doc.docx"
                with zipfile.ZipFile(doc, "w") as zf:
                    zf.writestr("startup.conf", "do atacante")
                ws, victim = Path(tmp) / "ws", Path(tmp) / "victim"
                ws.mkdir()
                victim.mkdir()
                (victim / "startup.conf").write_text("da vítima")
                (ws / "unpacked").symlink_to(victim)
                (ws / "sub").symlink_to(victim)
                result = subprocess.run([sys.executable, "-c", textwrap.dedent(f"""
                    import sys, zipfile
                    sys.path.insert(0, {str(SKILLS / f"{skill}/scripts")!r})
                    from pathlib import Path
                    from office.helpers import safe_extract
                    for dest in ("unpacked", "sub/novo", "real"):
                        try:
                            safe_extract(zipfile.ZipFile({str(doc)!r}), Path(dest))
                            print(dest, "extraído")
                        except ValueError:
                            print(dest, "recusado")
                """)], capture_output=True, text=True, timeout=60, cwd=ws)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.split("\n")[:3], ["unpacked recusado", "sub/novo recusado", "real extraído"])
                self.assertEqual((victim / "startup.conf").read_text(), "da vítima")
                self.assertFalse((victim / "novo").exists())

    def test_office_archive_limits_catch_split_bomb(self):
        # Várias entradas de exatamente 1 MiB escapavam da razão por entrada; a razão do arquivo inteiro pega.
        for skill in ("docx", "pptx", "xlsx"):
            with self.subTest(skill), tempfile.TemporaryDirectory() as tmp:
                bomb = Path(tmp) / "split.docx"
                with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i in range(16):
                        zf.writestr(f"word/media/z{i}.bin", b"\0" * (1024 * 1024))
                result = run_in(SKILLS / f"{skill}/scripts", f"""
                    import zipfile
                    from office.helpers import check_archive_limits
                    try:
                        check_archive_limits(zipfile.ZipFile({str(bomb)!r}))
                        print("aceito")
                    except ValueError as e:
                        print("recusado:", e)
                """)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "recusado: suspicious compression ratio for the archive as a whole")

    def test_office_extract_and_rezip_never_carry_planted_links(self):
        # unpacked/leak.txt já existe como link para um arquivo local; não pode acabar dentro do documento.
        for skill in ("docx", "pptx", "xlsx"):
            with self.subTest(skill), tempfile.TemporaryDirectory() as tmp:
                doc = Path(tmp) / "doc.docx"
                with zipfile.ZipFile(doc, "w") as zf:
                    zf.writestr("word/document.xml", "<w:document/>")
                secret = Path(tmp) / "secret.txt"
                secret.write_text("SENTINELA")
                unpacked = Path(tmp) / "unpacked"
                unpacked.mkdir()
                (unpacked / "leak.txt").symlink_to(secret)
                result = run_in(SKILLS / f"{skill}/scripts", f"""
                    import zipfile
                    from pathlib import Path
                    from office.helpers import rezip, safe_extract
                    for step in ("extract", "rezip"):
                        try:
                            if step == "extract":
                                safe_extract(zipfile.ZipFile({str(doc)!r}), Path({str(unpacked)!r}))
                            else:
                                rezip(Path({str(unpacked)!r}), Path({str(Path(tmp) / "out.docx")!r}))
                            print(step, "feito")
                        except ValueError:
                            print(step, "recusado")
                """)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.split(), ["extract", "recusado", "rezip", "recusado"])
                self.assertFalse((Path(tmp) / "out.docx").exists())

    def test_office_safe_extract_rejects_zip_bomb(self):
        for skill in ("docx", "pptx", "xlsx"):
            with self.subTest(skill), tempfile.TemporaryDirectory() as tmp:
                bomb = Path(tmp) / "bomb.docx"
                with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr("word/document.xml", "<w:document/>")
                    zf.writestr("word/media/zeros.bin", b"\0" * (16 * 1024 * 1024))  # ~16 KB comprimido
                out = Path(tmp) / "out"
                result = run_in(SKILLS / f"{skill}/scripts", f"""
                    import zipfile
                    from pathlib import Path
                    from office.helpers import safe_extract
                    try:
                        safe_extract(zipfile.ZipFile({str(bomb)!r}), Path({str(out)!r}))
                        print("extraído")
                    except ValueError as e:
                        print("recusado:", e)
                """)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(result.stdout.startswith("recusado: suspicious compression ratio"), result.stdout)
                self.assertFalse((out / "word/media/zeros.bin").exists())

    @unittest.skipUnless(importlib.util.find_spec("lxml"), "lxml não instalado")
    def test_office_validator_checks_references_without_rels_file(self):
        r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        for skill in ("docx", "pptx", "xlsx"):
            with self.subTest(skill), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "word").mkdir()
                (Path(tmp) / "word/document.xml").write_text(
                    f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
                    f' xmlns:r="{r_ns}"><w:hyperlink r:id="rId404"/></w:document>')
                result = run_in(SKILLS / f"{skill}/scripts/office", f"""
                    from validators.base import BaseSchemaValidator
                    print(BaseSchemaValidator({tmp!r}).validate_all_relationship_ids())
                """)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip().splitlines()[-1], "False")
                self.assertIn("rId404", result.stdout)

    @unittest.skipUnless(importlib.util.find_spec("lxml"), "lxml não instalado")
    def test_office_validator_allows_comments_by_the_same_author(self):
        for skill in ("docx", "pptx", "xlsx"):
            with self.subTest(skill), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "ppt/comments").mkdir(parents=True)
                (Path(tmp) / "ppt/comments/comment1.xml").write_text(
                    '<p:cmLst xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
                    '<p:cm authorId="0" idx="1"/><p:cm authorId="0" idx="2"/></p:cmLst>')
                result = run_in(SKILLS / f"{skill}/scripts/office", f"""
                    from validators.base import BaseSchemaValidator
                    print(BaseSchemaValidator({tmp!r}).validate_unique_ids())
                """)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip().splitlines()[-1], "True", result.stdout)

    @unittest.skipUnless(importlib.util.find_spec("lxml"), "lxml não instalado")
    def test_office_validator_decodes_uri_targets(self):
        # Target="media/image%201.png" aponta para word/media/image 1.png: referência válida, sem órfão.
        rel = "http://schemas.openxmlformats.org/package/2006/relationships"
        ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        for skill in ("docx", "pptx", "xlsx"):
            with self.subTest(skill), tempfile.TemporaryDirectory() as tmp:
                pkg = Path(tmp)
                (pkg / "_rels").mkdir()
                (pkg / "word/_rels").mkdir(parents=True)
                (pkg / "word/media").mkdir()
                (pkg / "_rels/.rels").write_text(
                    f'<Relationships xmlns="{rel}"><Relationship Id="rId1" Type="{ns}/officeDocument"'
                    ' Target="word/document.xml"/></Relationships>')
                (pkg / "word/document.xml").write_text("<doc/>")
                (pkg / "word/media/image 1.png").write_bytes(b"png")
                (pkg / "word/_rels/document.xml.rels").write_text(
                    f'<Relationships xmlns="{rel}"><Relationship Id="rId1" Type="{ns}/image"'
                    ' Target="media/image%201.png"/></Relationships>')
                result = run_in(SKILLS / f"{skill}/scripts/office", f"""
                    from validators.base import BaseSchemaValidator
                    print(BaseSchemaValidator({tmp!r}).validate_file_references())
                """)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip().splitlines()[-1], "True", result.stdout)

    @unittest.skipUnless(importlib.util.find_spec("lxml"), "lxml não instalado")
    def test_office_validator_rejects_reference_outside_package(self):
        # Target="../../outside.png" sai da extração; a imagem não vai no ZIP, então a referência está quebrada.
        rel = "http://schemas.openxmlformats.org/package/2006/relationships"
        img = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
        for skill in ("docx", "pptx", "xlsx"):
            with self.subTest(skill), tempfile.TemporaryDirectory() as tmp:
                pkg = Path(tmp) / "pkg"
                (pkg / "word/_rels").mkdir(parents=True)
                (pkg / "word/document.xml").write_text("<doc/>")
                (pkg / "word/_rels/document.xml.rels").write_text(
                    f'<Relationships xmlns="{rel}"><Relationship Id="rId1" Type="{img}"'
                    ' Target="../../outside.png"/></Relationships>')
                (Path(tmp) / "outside.png").write_bytes(b"png")
                result = run_in(SKILLS / f"{skill}/scripts/office", f"""
                    from validators.base import BaseSchemaValidator
                    print(BaseSchemaValidator({str(pkg)!r}).validate_file_references())
                """)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Broken reference to ../../outside.png", result.stdout)
                self.assertEqual(result.stdout.strip().splitlines()[-1], "False", result.stdout)

    def test_pptx_chart_checks_ignore_namespace_prefix(self):
        # chart: em vez de c: (mesmo URI) não pode esconder um dLblPos="outEnd" em barras empilhadas.
        ns = "http://schemas.openxmlformats.org/drawingml/2006/chart"
        body = ('<{p}chartSpace {decl}><{p}chart><{p}plotArea><{p}barChart><{p}grouping val="stacked"/>'
                '<{p}dLbls><{p}dLblPos val="outEnd"/></{p}dLbls>'
                '<{p}axId val="1"/><{p}axId val="2"/></{p}barChart>'
                '<{p}catAx><{p}axId val="1"/></{p}catAx><{p}valAx><{p}axId val="2"/></{p}valAx>'
                '</{p}plotArea></{p}chart></{p}chartSpace>')
        variants = {"chart": body.format(p="chart:", decl=f'xmlns:chart="{ns}"'),
                    "default": body.format(p="", decl=f'xmlns="{ns}"')}
        for skill in ("docx", "pptx", "xlsx"):
            for name, chart in variants.items():
                with self.subTest(skill=skill, prefix=name):
                    result = run_in(SKILLS / f"{skill}/scripts/office", f"""
                        from helpers.pptx_chart import find_chart_problems
                        print(find_chart_problems({{"ppt/charts/chart1.xml": {chart.encode()!r}}}))
                    """)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('dLblPos="outEnd"', result.stdout)

    def test_pptx_chart_3d_line_needs_three_live_axes(self):
        # line3DChart exige 3 eixos; com o 3º apontando para um eixo inexistente, o gráfico é descartado.
        chart = ('<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"><c:chart>'
                 '<c:plotArea><c:line3DChart><c:axId val="1"/><c:axId val="2"/><c:axId val="999"/></c:line3DChart>'
                 '<c:catAx><c:axId val="1"/></c:catAx><c:valAx><c:axId val="2"/></c:valAx>'
                 '<c:serAx><c:axId val="3"/></c:serAx></c:plotArea></c:chart></c:chartSpace>')
        for skill in ("docx", "pptx", "xlsx"):
            with self.subTest(skill):
                result = run_in(SKILLS / f"{skill}/scripts/office", f"""
                    from helpers.pptx_chart import find_chart_problems
                    print(find_chart_problems({{"ppt/charts/chart1.xml": {chart.encode()!r}}}))
                """)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("999 name no declared axis", result.stdout)

    def test_office_skill_md_unpack_command_rejects_zip_bomb(self):
        for skill, name in (("pptx", "deck.pptx"), ("docx", "doc.docx")):
            with self.subTest(skill), tempfile.TemporaryDirectory() as tmp:
                md = (SKILLS / skill / "SKILL.md").read_text()
                line = next(l for l in md.splitlines() if "safe_extract" in l and name in l)
                command = line.split("   #")[0].replace(name, str(Path(tmp) / name)).replace(
                    " unpacked", " " + str(Path(tmp) / "unpacked"))
                with zipfile.ZipFile(Path(tmp) / name, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr("media/zeros.bin", b"\0" * (16 * 1024 * 1024))
                result = subprocess.run(command, shell=True, cwd=SKILLS / skill, capture_output=True, text=True, timeout=60)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("suspicious compression ratio", result.stderr)
                self.assertFalse((Path(tmp) / "unpacked/media/zeros.bin").exists())
                # Um pacote comum continua sendo extraído pelo mesmo comando.
                with zipfile.ZipFile(Path(tmp) / name, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr("word/document.xml", "<x/>")
                result = subprocess.run(command, shell=True, cwd=SKILLS / skill, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((Path(tmp) / "unpacked/word/document.xml").exists())

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

    def test_docx_accept_changes_never_writes_through_output_link(self):
        # out.docx -> victim.txt: o alvo não pode receber os bytes, nem em falha nem em sucesso.
        for code in (1, 0):
            with self.subTest(soffice_exit=code), tempfile.TemporaryDirectory() as tmp:
                src, out, victim = Path(tmp) / "in.docx", Path(tmp) / "out.docx", Path(tmp) / "victim.txt"
                src.write_bytes(b"conteudo arbitrario")
                victim.write_text("da vítima")
                out.symlink_to(victim)
                result = run_in(SKILLS / "docx/scripts", f"""
                    import subprocess
                    from unittest import mock
                    import accept_changes
                    with mock.patch.object(accept_changes, "_setup_libreoffice_macro", return_value=True), \\
                         mock.patch.object(accept_changes.subprocess, "run",
                                           return_value=subprocess.CompletedProcess([], {code}, "", "falhou")):
                        print(accept_changes.accept_changes({str(src)!r}, {str(out)!r})[1])
                """)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(victim.read_text(), "da vítima")
                self.assertEqual(out.is_symlink(), code != 0)  # em sucesso o link é substituído pelo resultado
                self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                                 ["in.docx", "out.docx", "victim.txt"])  # nenhum temporário sobra

    def test_docx_comment_uses_linked_comments_part(self):
        # O documento aponta os comentários para word/comments1.xml; IDs e respostas devem usar essa parte.
        pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
        rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "word/_rels").mkdir(parents=True)
            (root / "word/_rels/document.xml.rels").write_text(
                f'<Relationships xmlns="{pkg}"><Relationship Id="rId1" Type="{rel}" Target="comments1.xml"/></Relationships>')
            (root / "word/comments1.xml").write_text(
                '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
                ' xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">'
                '<w:comment w:id="0"><w:p w14:paraId="0000AAAA"/></w:comment></w:comments>')
            result = run_in(SKILLS / "docx/scripts", f"""
                from comment import add_comment
                print(add_comment({tmp!r}, "nova", parent_id=0)[0])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "1")
            self.assertFalse((root / "word/comments.xml").exists())
            rels = ET.parse(root / "word/_rels/document.xml.rels").getroot()
            self.assertEqual([r.get("Target") for r in rels if r.get("Type") == rel], ["comments1.xml"])
            w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id"
            self.assertEqual([c.get(w) for c in ET.parse(root / "word/comments1.xml").getroot()], ["0", "1"])

    def test_docx_comment_replies_to_comment_without_para_id(self):
        # w14:paraId é opcional; o comentário 0 existe sem ele e a resposta precisa funcionar.
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        w14 = "{http://schemas.microsoft.com/office/word/2010/wordml}paraId"
        w15 = "http://schemas.microsoft.com/office/word/2012/wordml"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "word").mkdir()
            (root / "word/comments.xml").write_text(
                f'<w:comments xmlns:w="{w}"><w:comment w:id="0" w:author="A">'
                '<w:p><w:r><w:t>original</w:t></w:r></w:p></w:comment></w:comments>')
            result = run_in(SKILLS / "docx/scripts", f"""
                from comment import add_comment
                print(add_comment({tmp!r}, "resposta", parent_id=0)[0])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "1")
            comments = ET.parse(root / "word/comments.xml").getroot()
            parent_pid = comments.find(f"{{{w}}}comment").find(f"{{{w}}}p").get(w14)
            self.assertTrue(parent_pid)
            ex = ET.parse(root / "word/commentsExtended.xml").getroot()
            entries = [(e.get(f"{{{w15}}}paraId"), e.get(f"{{{w15}}}paraIdParent")) for e in ex]
            self.assertIn((parent_pid, None), entries)
            self.assertEqual([p for _, p in entries if p], [parent_pid])

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

    def test_list_tools_follows_every_page(self):
        # Sessões nos dois formatos da API do mcp: params=PaginatedRequestParams (novo) e cursor= (antigo).
        result = run_in(SKILLS / "mcp-builder/scripts", """
            import asyncio, sys, types
            mcp = types.ModuleType("mcp")
            mcp.ClientSession = mcp.StdioServerParameters = object
            mcp.types = types.SimpleNamespace(PaginatedRequestParams=lambda cursor: types.SimpleNamespace(cursor=cursor))
            sys.modules["mcp"] = mcp
            for name in ("mcp.client", "mcp.client.sse", "mcp.client.stdio", "mcp.client.streamable_http"):
                sys.modules[name] = types.SimpleNamespace(sse_client=None, stdio_client=None, streamablehttp_client=None)
            import connections
            Tool = lambda n: types.SimpleNamespace(name=n, description="", inputSchema={})
            PAGES = {None: ([Tool("a")], "p2"), "p2": ([Tool("b")], None)}
            def page(cursor):
                tools, nxt = PAGES[cursor]
                return types.SimpleNamespace(tools=tools, nextCursor=nxt)
            class New:
                async def list_tools(self, *, params=None):
                    return page(params.cursor if params else None)
            class Old:
                async def list_tools(self, cursor=None):
                    return page(cursor)
            for session in (New(), Old()):
                conn = object.__new__(connections.MCPConnectionStdio)
                conn.session = session
                print([t["name"] for t in asyncio.run(conn.list_tools())])
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["['a',", "'b']", "['a',", "'b']"])

class SkillCreatorTests(unittest.TestCase):
    def test_package_skill_does_not_follow_link_at_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "my-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text("---\nname: my-skill\ndescription: x\n---\n")
            sentinel = Path(tmp) / "sentinel.txt"
            sentinel.write_text("conteúdo do usuário")
            (skill / "my-skill.skill").symlink_to(sentinel)  # saída na própria pasta da skill
            result = run_in(SKILLS / "skill-creator", f"""
                import os, sys, types, zipfile
                sys.modules["scripts.quick_validate"] = types.SimpleNamespace(validate_skill=lambda p: (True, "ok"))
                from scripts.package_skill import package_skill
                os.chdir({str(skill)!r})
                out = package_skill({str(skill)!r})
                print(sorted(zipfile.ZipFile(out).namelist()))
            """)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(sentinel.read_text(), "conteúdo do usuário")
            self.assertFalse((skill / "my-skill.skill").is_symlink())
            self.assertEqual(result.stdout.strip().splitlines()[-1], "['my-skill/SKILL.md']")

    @unittest.skipUnless(shutil.which("node"), "node não disponível")
    def test_eval_runner_resume_recovers_artifacts_after_failed_write(self):
        scaffold = (SKILLS / "claude-api/shared/evals/report/runner-scaffold.mjs").read_text()
        filled = (scaffold
                  .replace("throw new Error('TODO: loadCases');", "return [{ id: 'case-a', prompt: 'p' }];")
                  .replace("throw new Error('TODO: runCase');",
                           "return { output: 'saida', transcript: [{ role: 'user', content: 'p' }],"
                           " model: 'm', usage: { input_tokens: 1, output_tokens: 1 }, stop_reason: 'end_turn' };")
                  .replace("throw new Error('TODO: gradeCase');", "return { grade: { pass: 1 } };"))
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "bin/run-eval.mjs"
            runner.parent.mkdir()
            runner.write_text(filled)
            flow = Path(tmp) / "flow"
            trace = flow / "baseline/traces/case-a_rep0.json"
            trace.mkdir(parents=True)  # a gravação do transcript falha (EISDIR) na primeira execução
            run = lambda: subprocess.run(["node", str(runner), "--flow", str(flow), "--variant", "baseline",
                                          "--approve-harness"], capture_output=True, text=True, timeout=60, cwd=tmp)
            first = run()
            trace.rmdir()  # a causa foi removida; a retomada deve refazer o caso
            second = run()
            self.assertEqual(second.returncode, 0, first.stderr + second.stderr)
            self.assertTrue(trace.is_file())
            self.assertEqual((flow / "baseline/ref/case-a").read_text(), "saida")
            rows = (flow / "baseline/results.jsonl").read_text().splitlines()
            self.assertEqual(len(rows), 1)

    @unittest.skipUnless(shutil.which("node"), "node não disponível")
    def test_eval_report_lite_keeps_variant_with_only_errors(self):
        # Uma variante em que todas as tentativas falharam só tem errors.jsonl; o relatório deve mostrá-la.
        builder = SKILLS / "claude-api/shared/evals/report/build-report-lite.mjs"
        with tempfile.TemporaryDirectory() as tmp:
            flow = Path(tmp) / "flow"
            (flow / "baseline").mkdir(parents=True)
            (flow / "v1").mkdir()
            (flow / "baseline/results.jsonl").write_text(json.dumps(
                {"prompt_id": "c1", "status": "ok", "grade": {"pass": 1}}) + "\n")
            (flow / "v1/errors.jsonl").write_text(json.dumps(
                {"prompt_id": "c1", "failure_class": "timeout"}) + "\n")
            result = subprocess.run(["node", str(builder), "flow"], capture_output=True, text=True,
                                    timeout=60, cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((flow / "trajectory/scores.tsv").read_text().splitlines(),
                             ["id\tsplit\tbaseline\tv1", "c1\tall\t1.000\t"])
            self.assertIn("timeout 1", (flow / "report.html").read_text())

    @unittest.skipUnless(shutil.which("node"), "node não disponível")
    def test_eval_runner_rejects_ids_that_share_a_ref_path(self):
        # 'invoice' e 'invoice.txt' cairiam no mesmo baseline/ref/invoice.txt.
        scaffold = (SKILLS / "claude-api/shared/evals/report/runner-scaffold.mjs").read_text()
        filled = (scaffold
                  .replace("throw new Error('TODO: loadCases');",
                           "return [{ id: 'invoice.txt', prompt: 'a' }, { id: 'invoice', prompt: 'b' }];")
                  .replace("throw new Error('TODO: runCase');", "throw new Error('não deveria rodar');")
                  .replace("throw new Error('TODO: gradeCase');", "return { grade: { pass: 1 } };"))
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "bin/run-eval.mjs"
            runner.parent.mkdir()
            runner.write_text(filled)
            result = subprocess.run(["node", str(runner), "--flow", str(Path(tmp) / "flow"), "--variant", "baseline",
                                     "--approve-harness"], capture_output=True, text=True, timeout=60, cwd=tmp)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("collides", result.stderr)
            self.assertFalse((Path(tmp) / "flow/baseline/results.jsonl").exists())

    @unittest.skipUnless(shutil.which("node"), "node não disponível")
    def test_eval_runner_error_row_keeps_judge_usage(self):
        # O juiz concluiu, mas a gravação do transcript falhou: o gasto do juiz deve ficar no errors.jsonl.
        scaffold = (SKILLS / "claude-api/shared/evals/report/runner-scaffold.mjs").read_text()
        filled = (scaffold
                  .replace("throw new Error('TODO: loadCases');", "return [{ id: 'case-a', prompt: 'p' }];")
                  .replace("throw new Error('TODO: runCase');",
                           "return { output: 'saida', transcript: [{ role: 'user', content: 'p' }],"
                           " model: 'm', usage: { input_tokens: 1, output_tokens: 1 }, stop_reason: 'end_turn' };")
                  .replace("throw new Error('TODO: gradeCase');",
                           "return { grade: { pass: 1 }, judge_model: 'juiz', judge_usage: { input_tokens: 7 } };"))
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "bin/run-eval.mjs"
            runner.parent.mkdir()
            runner.write_text(filled)
            flow = Path(tmp) / "flow"
            (flow / "baseline/traces/case-a_rep0.json").mkdir(parents=True)  # EISDIR ao gravar o transcript
            subprocess.run(["node", str(runner), "--flow", str(flow), "--variant", "baseline", "--approve-harness"],
                           capture_output=True, text=True, timeout=60, cwd=tmp)
            row = json.loads((flow / "baseline/errors.jsonl").read_text().splitlines()[0])
            self.assertEqual((row.get("judge_model"), row.get("judge_usage")), ("juiz", {"input_tokens": 7}))

    def test_pptx_duplicate_slide_drops_notes_with_spaced_type(self):
        # Type = "…/notesSlide" (espaços em volta do =) é XML válido; a nota não pode ser compartilhada.
        result = run_in(SKILLS / "pptx/scripts", """
            from add_slide import NOTES_SLIDE_TYPE_RE
            ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            print(bool(NOTES_SLIDE_TYPE_RE.search(f'<Relationship Id="rId2" Type = "{ns}/notesSlide" Target="x"/>')),
                  bool(NOTES_SLIDE_TYPE_RE.search(f'<Relationship Id="rId1" Type="{ns}/slideLayout" Target="y"/>')))
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True False")

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

    def test_run_single_query_error_result_is_a_failure(self):
        # Um evento result com is_error é falha da execução, não "não acionou" (que aprovaria should_trigger: false).
        event = {"type": "result", "subtype": "error_during_execution", "is_error": True}
        with tempfile.TemporaryDirectory() as tmp:
            result = run_in(SKILLS / "skill-creator", f"""
                import io, json
                from unittest import mock
                from scripts import run_eval
                class Done:
                    stdout = io.BytesIO(json.dumps({event!r}).encode())
                    def poll(self):
                        return 1
                with mock.patch.object(run_eval.subprocess, "Popen", return_value=Done()):
                    try:
                        print(run_eval.run_single_query("q", "demo", "d", 5, {tmp!r}))
                    except RuntimeError as e:
                        print("erro:", e)
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "erro: claude -p failed: error_during_execution")

    def test_viewer_run_ids_stay_distinct(self):
        # eval-a/b-c e eval-a-b/c viravam o mesmo id e um feedback sobrescrevia o outro.
        with tempfile.TemporaryDirectory() as tmp:
            for rel in ("eval-a/b-c", "eval-a-b/c", "eval-0/with_skill"):
                (Path(tmp) / rel / "outputs").mkdir(parents=True)
                (Path(tmp) / rel / "outputs/answer.txt").write_text("x")
            result = run_in(SKILLS / "skill-creator/eval-viewer", f"""
                from pathlib import Path
                from generate_review import find_runs
                print(sorted(r["id"] for r in find_runs(Path({tmp!r}))), all("_path" not in r for r in find_runs(Path({tmp!r}))))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "['eval-0-with_skill', 'eval-a-b/c', 'eval-a/b-c'] True")

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

    def test_viewer_static_output_never_follows_link(self):
        # review.html -> victim.txt: o HTML deve substituir o link, não o alvo.
        script = SKILLS / "skill-creator/eval-viewer/generate_review.py"
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            (ws / "eval-0/outputs").mkdir(parents=True)
            (ws / "eval-0/outputs/out.txt").write_text("ok")
            victim = Path(tmp) / "victim.txt"
            victim.write_text("da vítima")
            out = ws / "review.html"
            out.symlink_to(victim)
            result = subprocess.run([sys.executable, str(script), str(ws), "--static", str(out)],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(victim.read_text(), "da vítima")
            self.assertFalse(out.is_symlink())
            self.assertIn("<html", out.read_text().lower())

    def test_viewer_previous_iteration_ignores_linked_feedback(self):
        # Um feedback.json da iteração anterior que é link levava o feedback de outro lugar para o HTML.
        with tempfile.TemporaryDirectory() as tmp:
            prev = Path(tmp) / "prev"
            prev.mkdir()
            (Path(tmp) / "private.json").write_text(json.dumps(
                {"reviews": [{"run_id": "r", "feedback": "SENTINELA"}]}))
            (prev / "feedback.json").symlink_to(Path(tmp) / "private.json")
            result = run_in(SKILLS / "skill-creator/eval-viewer", f"""
                from pathlib import Path
                from generate_review import load_previous_iteration
                print(load_previous_iteration(Path({str(prev)!r})))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("SENTINELA", result.stdout)
            (prev / "feedback.json").unlink()
            (prev / "feedback.json").write_text(json.dumps({"reviews": [{"run_id": "r", "feedback": "ok"}]}))
            result = run_in(SKILLS / "skill-creator/eval-viewer", f"""
                from pathlib import Path
                from generate_review import load_previous_iteration
                print(load_previous_iteration(Path({str(prev)!r}))["r"]["feedback"])
            """)
            self.assertEqual(result.stdout.strip(), "ok")

    def test_viewer_static_refuses_linked_benchmark(self):
        # Um benchmark.json que é link levava o JSON de fora do workspace para o HTML estático.
        script = SKILLS / "skill-creator/eval-viewer/generate_review.py"
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            (ws / "eval-0/outputs").mkdir(parents=True)
            (ws / "eval-0/outputs/out.txt").write_text("ok")
            (Path(tmp) / "private.json").write_text('{"segredo": "SENTINELA"}')
            (ws / "benchmark.json").symlink_to(Path(tmp) / "private.json")
            out = Path(tmp) / "view.html"
            run = lambda: subprocess.run([sys.executable, str(script), str(ws), "--benchmark",
                                          str(ws / "benchmark.json"), "--static", str(out)],
                                         capture_output=True, text=True, timeout=60)
            result = run()
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertFalse(out.exists() and "SENTINELA" in out.read_text())
            (ws / "benchmark.json").unlink()
            (ws / "benchmark.json").write_text('{"normal": "BENCH"}')
            result = run()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("BENCH", out.read_text())

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
              return {ok: true, status: 200, json: async () => ({})};
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

    def test_run_single_query_failed_process_is_an_error_not_a_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_in(SKILLS / "skill-creator", f"""
                import io
                from unittest import mock
                from scripts import run_eval
                class Crashed:  # claude -p que terminou com erro, sem nenhum evento
                    stdout = io.BytesIO(b"")
                    def poll(self):
                        return 1
                    def wait(self, timeout=None):
                        return 1
                with mock.patch.object(run_eval.subprocess, "Popen", return_value=Crashed()):
                    try:
                        print(run_eval.run_single_query("q", "demo", "d", 5, {tmp!r}))
                    except RuntimeError as e:
                        print("erro:", e)
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "erro: claude -p exited with code 1")

    @unittest.skipUnless(shutil.which("node"), "node não disponível")
    def test_viewer_final_submit_falls_back_to_download_on_http_error(self):
        html = (SKILLS / "skill-creator/eval-viewer/viewer.html").read_text()
        state = re.search(r"// ---- State ----\n(.*?)\n\n", html, re.S).group(1)
        done = re.search(r"function showDoneDialog\(\) \{.*?\n    \}", html, re.S).group(0)
        script = textwrap.dedent("""
            const EMBEDDED_DATA = {skill_name: "s", runs: [{id: "r1"}]};
            const location = {search: ""};
            async function fetch() { return {ok: false, status: 500}; }
            let downloaded = null;
            class Blob { constructor(parts) { this.text = parts.join(""); } }
            const URL = {createObjectURL(b) { downloaded = b.text; return "blob:x"; }, revokeObjectURL() {}};
            const els = {feedback: {value: "nota"}};
            const document = {
              getElementById(id) { return els[id] || (els[id] = {value: "", classList: {add() {}}}); },
              createElement() { return {click() {}}; },
            };
        """) + state + "\n" + done + textwrap.dedent("""
            showDoneDialog();
            setTimeout(() => process.stdout.write(String(downloaded)), 100);
        """)
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["reviews"][0]["feedback"], "nota")

    def test_benchmark_delta_puts_version_under_test_first(self):
        # old_skill vem antes de with_skill em ordem alfabética; o delta não pode sair invertido.
        with tempfile.TemporaryDirectory() as tmp:
            for config, rate in (("with_skill", 1.0), ("old_skill", 0.0)):
                d = Path(tmp) / "eval-0" / config
                (d / "outputs").mkdir(parents=True)
                (d / "grading.json").write_text(json.dumps({"summary": {"pass_rate": rate}}))
            result = run_in(SKILLS / "skill-creator", f"""
                from pathlib import Path
                from scripts.aggregate_benchmark import aggregate_results, load_run_results
                results = load_run_results(Path({tmp!r}))
                print(list(results), aggregate_results(results)["delta"]["pass_rate"])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "['with_skill', 'old_skill'] +1.00")

    def test_benchmark_unmeasured_baseline_has_no_delta(self):
        # without_skill tem run-1 sem grading.json: não foi medida, então não há melhoria a mostrar.
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "eval-0" / "with_skill" / "run-1"
            (d / "outputs").mkdir(parents=True)
            (d / "grading.json").write_text(json.dumps({"summary": {"pass_rate": 1.0}}))
            (Path(tmp) / "eval-0" / "without_skill" / "run-1").mkdir(parents=True)
            result = run_in(SKILLS / "skill-creator", f"""
                from pathlib import Path
                from scripts.aggregate_benchmark import generate_benchmark, generate_markdown
                b = generate_benchmark(Path({tmp!r}))
                delta = b["run_summary"]["delta"]
                print(list(b["run_summary"]), delta["pass_rate"], delta["time_seconds"])
                print("—s" in generate_markdown(b))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip().split("\n")[-2:],
                             ["['with_skill', 'without_skill', 'delta'] — —", "False"])

    def test_docx_comment_reply_uses_last_paragraph_para_id(self):
        # commentsExtended registra o comentário pelo paraId do último parágrafo (B), não do primeiro (A).
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        w14 = "http://schemas.microsoft.com/office/word/2010/wordml"
        w15 = "http://schemas.microsoft.com/office/word/2012/wordml"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "word").mkdir()
            (root / "word/comments.xml").write_text(
                f'<w:comments xmlns:w="{w}" xmlns:w14="{w14}"><w:comment w:id="0" w:author="A">'
                '<w:p w14:paraId="0000000A"/><w:p w14:paraId="0000000B"/></w:comment></w:comments>')
            (root / "word/commentsExtended.xml").write_text(
                f'<w15:commentsEx xmlns:w15="{w15}"><w15:commentEx w15:paraId="0000000B" w15:done="0"/>'
                '</w15:commentsEx>')
            result = run_in(SKILLS / "docx/scripts", f"""
                from comment import add_comment
                print(add_comment({tmp!r}, "resposta", parent_id=0)[0])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            ex = ET.parse(root / "word/commentsExtended.xml").getroot()
            parents = [e.get(f"{{{w15}}}paraIdParent") for e in ex if e.get(f"{{{w15}}}paraIdParent")]
            self.assertEqual(parents, ["0000000B"])

    def test_benchmark_delta_needs_same_graded_runs(self):
        # eval-1 de with_skill não foi avaliada: só eval-0 é pareada e empata, então não há delta.
        with tempfile.TemporaryDirectory() as tmp:
            for eval_id, config, rate in ((0, "with_skill", 1.0), (0, "without_skill", 1.0),
                                          (1, "with_skill", None), (1, "without_skill", 0.0)):
                d = Path(tmp) / f"eval-{eval_id}" / config / "run-1"
                (d / "outputs").mkdir(parents=True)
                if rate is not None:
                    (d / "grading.json").write_text(json.dumps({"summary": {"pass_rate": rate}}))
            result = run_in(SKILLS / "skill-creator", f"""
                from pathlib import Path
                from scripts.aggregate_benchmark import aggregate_results, load_run_results
                delta = aggregate_results(load_run_results(Path({tmp!r})))["delta"]
                print(delta["pass_rate"], delta["time_seconds"])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip().splitlines()[-1], "— —")

    def test_benchmark_never_mixes_output_chars_into_tokens(self):
        # Só a baseline tem tokens reais; a outra só tem output_chars. O delta de tokens não é medido.
        with tempfile.TemporaryDirectory() as tmp:
            for config, grading, timing in (
                ("with_skill", {"summary": {"pass_rate": 1.0}, "execution_metrics": {"output_chars": 4000}}, None),
                ("without_skill", {"summary": {"pass_rate": 1.0}, "execution_metrics": {"output_chars": 4000}},
                 {"total_tokens": 1000})):
                d = Path(tmp) / "eval-0" / config
                (d / "outputs").mkdir(parents=True)
                (d / "grading.json").write_text(json.dumps(grading))
                if timing:
                    (d / "timing.json").write_text(json.dumps(timing))
            result = run_in(SKILLS / "skill-creator", f"""
                from pathlib import Path
                from scripts.aggregate_benchmark import aggregate_results, load_run_results
                results = load_run_results(Path({tmp!r}))
                summary = aggregate_results(results)
                print(summary["delta"]["tokens"], summary["with_skill"]["tokens"]["mean"],
                      results["with_skill"][0]["output_chars"])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split(), ["—", "0.0", "4000"])

    def test_parse_skill_md_keeps_paragraphs_of_block_description(self):
        # Uma linha vazia dentro de "description: |" cortava o resto da descrição.
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "SKILL.md").write_text(
                "---\nname: demo\ndescription: |\n  Use for invoices.\n\n  Also use for receipts and refunds.\n"
                "license: x\n---\nbody\n")
            result = run_in(SKILLS / "skill-creator", f"""
                from pathlib import Path
                from scripts.utils import parse_skill_md
                print(parse_skill_md(Path({tmp!r}))[1])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "Use for invoices. Also use for receipts and refunds.")

    def test_benchmark_outputs_never_follow_links(self):
        # benchmark.json -> victim.json: o relatório substitui o link, não o alvo.
        with tempfile.TemporaryDirectory() as tmp:
            bench = Path(tmp) / "iteration-1"
            d = bench / "eval-0" / "with_skill"
            (d / "outputs").mkdir(parents=True)
            (d / "grading.json").write_text(json.dumps({"summary": {"pass_rate": 1.0}}))
            victim = Path(tmp) / "victim.json"
            victim.write_text("da vítima")
            (bench / "benchmark.json").symlink_to(victim)
            (bench / "benchmark.md").symlink_to(victim)
            result = subprocess.run([sys.executable, "-m", "scripts.aggregate_benchmark", str(bench)],
                                    capture_output=True, text=True, timeout=60, cwd=SKILLS / "skill-creator")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(victim.read_text(), "da vítima")
            self.assertFalse((bench / "benchmark.json").is_symlink())
            self.assertIn("run_summary", (bench / "benchmark.json").read_text())

    def test_viewer_never_kills_the_process_on_its_port(self):
        # A porta ocupada cai no fallback para uma porta livre; o script não envia sinal a ninguém.
        source = (SKILLS / "skill-creator/eval-viewer/generate_review.py").read_text()
        for forbidden in ("os.kill", "lsof", "_kill_port"):
            self.assertNotIn(forbidden, source)
        self.assertIn('HTTPServer(("127.0.0.1", 0), handler)', source)

    def test_viewer_lists_outputs_in_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "eval-0/with_skill/outputs"
            (out / "site").mkdir(parents=True)
            (out / "site/index.html").write_text("<p>ok</p>")
            (out / "notes.txt").write_text("x")
            result = run_in(SKILLS / "skill-creator/eval-viewer", f"""
                from pathlib import Path
                from generate_review import find_runs
                print([o["name"] for o in find_runs(Path({tmp!r}))[0]["outputs"]])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "['notes.txt', 'site/index.html']")

    def test_benchmark_finds_cases_with_descriptive_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp) / "invoice-summary"
            case.mkdir()
            (case / "eval_metadata.json").write_text(json.dumps({"eval_id": 0, "prompt": "p"}))
            for config, rate in (("with_skill", 1.0), ("without_skill", 0.0)):
                (case / config / "outputs").mkdir(parents=True)
                (case / config / "grading.json").write_text(json.dumps({"summary": {"pass_rate": rate}}))
            result = run_in(SKILLS / "skill-creator", f"""
                from pathlib import Path
                from scripts.aggregate_benchmark import load_run_results
                print(sorted((k, len(v)) for k, v in load_run_results(Path({tmp!r})).items()))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "[('with_skill', 1), ('without_skill', 1)]")

    def test_split_eval_set_keeps_training_cases_for_small_sets(self):
        result = run_in(SKILLS / "skill-creator", """
            from scripts.run_loop import split_eval_set
            for n in (1, 2, 5):
                cases = [{"query": f"p{i}", "should_trigger": True} for i in range(n)]
                cases += [{"query": f"n{i}", "should_trigger": False} for i in range(n)]
                train, test = split_eval_set(cases, 0.4)
                print(n, len(train), len(test))
        """)
        self.assertEqual(result.returncode, 0, result.stderr)
        # 1+1: nada reservado (o treino nunca fica vazio); 2+2: 1 de cada no teste; 5+5: 2 de cada.
        self.assertEqual(result.stdout.split(), ["1", "2", "0", "2", "2", "2", "5", "6", "4"])

    def test_viewer_never_embeds_files_behind_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp) / "secret.env"
            secret.write_text("TOKEN=segredo")
            outside = Path(tmp) / "fora"
            outside.mkdir()
            (outside / "chave.txt").write_text("CHAVE=segredo")
            out = Path(tmp) / "ws/eval-0/with_skill/outputs"
            out.mkdir(parents=True)
            (out / "ok.txt").write_text("resultado")
            (out / "link.txt").symlink_to(secret)
            (out / "pasta").symlink_to(outside, target_is_directory=True)
            result = run_in(SKILLS / "skill-creator/eval-viewer", f"""
                import json
                from pathlib import Path
                from generate_review import find_runs
                print(json.dumps(find_runs(Path({str(Path(tmp) / "ws")!r}))[0]["outputs"]))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("segredo", result.stdout)
            outputs = {o["name"]: o for o in json.loads(result.stdout)}
            self.assertEqual(outputs["ok.txt"]["content"], "resultado")
            self.assertEqual(outputs["link.txt"]["type"], "error")

    def test_viewer_rejects_outputs_dir_that_is_a_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp) / "private"
            private.mkdir()
            (private / "secret.env").write_text("TOKEN=segredo")
            run = Path(tmp) / "ws/eval-0/with_skill"
            run.mkdir(parents=True)
            (run / "outputs").symlink_to(private, target_is_directory=True)
            result = run_in(SKILLS / "skill-creator/eval-viewer", f"""
                import json
                from pathlib import Path
                from generate_review import find_runs
                print(json.dumps([r["outputs"] for r in find_runs(Path({str(Path(tmp) / "ws")!r}))]))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("segredo", result.stdout)
            self.assertNotIn("VE9LRU4", result.stdout)  # "TOKEN" em base64

    @unittest.skipUnless(shutil.which("node"), "node não disponível")
    def test_viewer_grade_counts_cannot_inject_html(self):
        html = (SKILLS / "skill-creator/eval-viewer/viewer.html").read_text()
        body = re.search(r"function renderGrades\(run\) \{.*?\n    \}", html, re.S).group(0)
        esc = re.search(r"function escapeHtml\(text\) \{.*?\n    \}", html, re.S).group(0)
        script = textwrap.dedent("""
            const els = {};
            const document = {
              getElementById(id) { return els[id] || (els[id] = {style: {}, classList: {add() {}, remove() {}}}); },
              createElement() { return { set textContent(t) { this.t = String(t); },
                get innerHTML() { return this.t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); } }; },
            };
        """) + esc + "\n" + body + textwrap.dedent("""
            renderGrades({grading: {summary: {pass_rate: 1, passed: '<img src=x onerror="globalThis.injected=true">',
                                              failed: 0, total: 1}, expectations: []}});
            process.stdout.write(els["grades-content"].innerHTML);
        """)
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("<img", result.stdout)
        self.assertIn("0 passed, 0 failed of 1", result.stdout)

    def test_viewer_metadata_files_behind_links_are_not_embedded(self):
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp) / "private.json"
            private.write_text(json.dumps({"api_key": "PRIVATE_SENTINEL_7c36", "prompt": "PRIVATE_SENTINEL_7c36"}))
            run = Path(tmp) / "ws/eval-0/with_skill"
            (run / "outputs").mkdir(parents=True)
            for name in ("grading.json", "eval_metadata.json"):
                (run / name).symlink_to(private)
            transcript = Path(tmp) / "transcript.md"
            transcript.write_text("## Eval Prompt\n\nPRIVATE_SENTINEL_7c36\n")
            (run / "transcript.md").symlink_to(transcript)
            result = run_in(SKILLS / "skill-creator/eval-viewer", f"""
                import json
                from pathlib import Path
                from generate_review import find_runs
                print(json.dumps(find_runs(Path({str(Path(tmp) / "ws")!r}))))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("PRIVATE_SENTINEL_7c36", result.stdout)

    @unittest.skipUnless(shutil.which("node"), "node não disponível")
    def test_viewer_benchmark_values_cannot_inject_html(self):
        html = (SKILLS / "skill-creator/eval-viewer/viewer.html").read_text()
        body = re.search(r"function renderBenchmark\(\) \{.*?\n    \}", html, re.S).group(0)
        esc = re.search(r"function escapeHtml\(text\) \{.*?\n    \}", html, re.S).group(0)
        bad = '<img src=x onerror="globalThis.injected=1">'
        benchmark = {
            "metadata": {"timestamp": bad, "evals_run": [bad], "runs_per_configuration": bad},
            "run_summary": {bad: {}, "without_skill": {}, "delta": {"pass_rate": bad, "time_seconds": bad, "tokens": bad}},
            "runs": [{"eval_id": 1, "configuration": bad, "run_number": bad,
                      "result": {"pass_rate": 1, "passed": bad, "total": bad, "errors": bad}, "expectations": []}],
            "notes": [],
        }
        script = textwrap.dedent("""
            const els = {};
            const document = {
              getElementById(id) { return els[id] || (els[id] = {style: {}, classList: {add() {}, remove() {}}}); },
              createElement() { return { set textContent(t) { this.t = String(t); },
                get innerHTML() { return this.t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); } }; },
            };
        """) + f"const EMBEDDED_DATA = {{benchmark: {json.dumps(benchmark)}}};\n" + esc + "\n" + body + textwrap.dedent("""
            renderBenchmark();
            process.stdout.write(els["benchmark-content"].innerHTML);
        """)
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("&lt;img", result.stdout)  # o valor aparece, mas como texto
        self.assertNotIn("<img", result.stdout)

    @unittest.skipUnless(shutil.which("node"), "node não disponível")
    def test_viewer_closing_done_dialog_keeps_submission_complete(self):
        html = (SKILLS / "skill-creator/eval-viewer/viewer.html").read_text()
        state = re.search(r"// ---- State ----\n(.*?)\n\n", html, re.S).group(1)
        funcs = [re.search(rf"function {name}\(\) \{{.*?\n    \}}", html, re.S).group(0)
                 for name in ("saveCurrentFeedback", "showDoneDialog", "closeDoneDialog")]
        script = textwrap.dedent("""
            const EMBEDDED_DATA = {skill_name: "s", runs: [{id: "r1"}, {id: "r2"}]};
            const location = {search: ""};
            const posts = [];
            async function fetch(url, opts) {
              if (opts && opts.method === "POST") posts.push(JSON.parse(opts.body).status);
              return {ok: true, status: 200};
            }
            const els = {feedback: {value: "nota"}};
            const document = {getElementById(id) {
              return els[id] || (els[id] = {value: "", classList: {add() {}, remove() {}}, set textContent(t) {}});
            }};
        """) + state + "\n" + "\n".join(funcs) + textwrap.dedent("""
            showDoneDialog();
            setTimeout(() => { closeDoneDialog(); setTimeout(() => process.stdout.write(JSON.stringify(posts)), 50); }, 50);
        """)
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["complete"])

    def test_run_loop_report_never_follows_planted_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "victim.txt"
            target.write_text("original")
            skill = Path(tmp) / "demo"
            skill.mkdir()
            (skill / "SKILL.md").write_text("---\nname: demo\ndescription: d\n---\n")
            (Path(tmp) / "evals.json").write_text("[]")
            # O nome antigo era previsível: skill_description_report_<skill>_<timestamp>.html no tmp compartilhado.
            (Path(tmp) / "skill_description_report_demo_20260101_000000.html").symlink_to(target)
            result = run_in(SKILLS / "skill-creator", f"""
                import os, sys, tempfile
                from unittest import mock
                tempfile.tempdir = {tmp!r}
                from scripts import run_loop
                sys.argv = ["run_loop", "--eval-set", {str(Path(tmp) / "evals.json")!r},
                            "--skill-path", {str(skill)!r}, "--model", "m"]
                with mock.patch.object(run_loop.time, "strftime", return_value="20260101_000000"), \\
                     mock.patch.object(run_loop.webbrowser, "open"), \\
                     mock.patch.object(run_loop, "run_loop", side_effect=SystemExit(0)), \\
                     mock.patch.object(run_loop, "parse_skill_md", return_value=("demo", "d", "")):
                    try:
                        run_loop.main()
                    except SystemExit:
                        pass
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_text(), "original")

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

    def test_viewer_feedback_never_follows_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            ws.mkdir()
            outside = Path(tmp) / "settings.json"
            outside.write_text('{"keep": true}')
            (ws / "feedback.json").symlink_to(outside)
            result = run_in(SKILLS / "skill-creator/eval-viewer", f"""
                import json, threading, urllib.request
                from functools import partial
                from http.server import HTTPServer
                from pathlib import Path
                from generate_review import ReviewHandler
                fb = Path({str(ws)!r}) / "feedback.json"
                handler = partial(ReviewHandler, Path({str(ws)!r}), "s", fb, {{}}, None, "t")
                server = HTTPServer(("127.0.0.1", 0), handler)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                base = "http://127.0.0.1:%d/api/feedback?token=t" % server.server_address[1]
                got = urllib.request.urlopen(base).read().decode()
                body = json.dumps({{"reviews": [{{"run_id": "r1", "feedback": "ok"}}]}}).encode()
                code = urllib.request.urlopen(urllib.request.Request(base, data=body)).status
                print(got, code, fb.is_symlink())
                server.shutdown()
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split(), ["{}", "200", "False"])
            self.assertEqual(outside.read_text(), '{"keep": true}')
            self.assertEqual(json.loads((ws / "feedback.json").read_text())["reviews"][0]["feedback"], "ok")

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

    @unittest.skipUnless(shutil.which("node"), "node não disponível")
    def test_viewer_xlsx_never_renders_spreadsheet_html(self):
        # O SheetJS transforma um hyperlink javascript: em <a href>; a célula deve virar só texto.
        html = (SKILLS / "skill-creator/eval-viewer/viewer.html").read_text()
        body = re.search(r"function renderXlsx\(container, b64Data\) \{.*?\n    \}", html, re.S).group(0)
        script = textwrap.dedent("""
            const atob = (s) => s;
            const link = '<a href="javascript:alert(1)">x</a>';
            const XLSX = {read: () => ({SheetNames: ["S"], Sheets: {S: {}}}),
                          utils: {sheet_to_html: () => "<table><tr><td>" + link + "</td></tr></table>",
                                  sheet_to_json: () => [["x", 1]]}};
            let rawHtml = "";
            const el = () => ({children: [], text: "",
              set innerHTML(h) { rawHtml += h; }, set textContent(t) { this.text = t; },
              appendChild(c) { this.children.push(c); }, style: {}});
            const document = {createElement: el};
            const container = el();
        """) + body + textwrap.dedent("""
            renderXlsx(container, "");
            const cells = container.children[0].children[0].children[0].children.map(c => c.text);
            process.stdout.write(JSON.stringify([rawHtml, cells, container.text]));
        """)
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["", ["x", "1"], ""])

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
    def test_xlsx_recalc_refuses_network_formulas(self):
        # =WEBSERVICE(...) faria o LibreOffice buscar a URL ao recalcular e gravar a resposta no arquivo.
        with tempfile.TemporaryDirectory() as tmp:
            bad, ok = Path(tmp) / "bad.xlsx", Path(tmp) / "ok.xlsx"
            result = run_in(SKILLS / "xlsx/scripts", f"""
                from unittest import mock
                from openpyxl import Workbook
                import recalc
                for path, formula in (({str(bad)!r}, '=WEBSERVICE("http://127.0.0.1:1/")'), ({str(ok)!r}, "=SUM(1,2)")):
                    wb = Workbook(); wb.active["A1"] = formula; wb.active["A2"] = "texto WEBSERVICE(x)"; wb.save(path)
                with mock.patch.object(recalc, "_recalc_with_profile", side_effect=AssertionError("rodou")):
                    out = recalc.recalc({str(bad)!r}, force=True)
                print(out.get("network_formula_parts"), recalc.network_formula_parts({str(ok)!r}))
                import zipfile
                with zipfile.ZipFile({str(bad)!r}) as src, zipfile.ZipFile({str(bad)!r} + ".enc.xlsx", "w") as dst:
                    for item in src.infolist():
                        data = src.read(item)
                        if item.filename == "xl/worksheets/sheet1.xml":
                            data = data.replace(b"<f>WEBSERVICE", b"<f>WEBSERV&#73;CE")
                        dst.writestr(item, data)
                print("codificada:", recalc.network_formula_parts({str(bad)!r} + ".enc.xlsx"))
                # Referência numérica: WEBSERV&#73;CE vira WEBSERVICE depois de interpretar o XML.
                print(recalc._calls_network(b'<f>WEBSERV&#73;CE("http://127.0.0.1/")</f>'),
                      recalc._calls_network(b'<f><![CDATA[_xlfn.DDE("x")]]></f>'),
                      recalc._calls_network(b'<!DOCTYPE f [<!ENTITY e "WEBSERVICE">]><f>&e;(1)</f>'),
                      recalc._calls_network(b'<c><v>WEBSERVICE(1)</v></c>'))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip().splitlines(),
                             ["['xl/worksheets/sheet1.xml'] []", "codificada: ['xl/worksheets/sheet1.xml']",
                              "True True True False"])

    def test_xlsx_network_scan_ignores_part_names(self):
        # sheet1.XML (maiúsculas), parte fora de xl/, fórmula ODF em atributo e arquivo que não é ZIP.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.xlsx"
            result = run_in(SKILLS / "xlsx/scripts", f"""
                import zipfile
                from openpyxl import Workbook
                import recalc
                wb = Workbook(); wb.active["A1"] = '=WEBSERVICE("http://127.0.0.1/")'; wb.save({str(base)!r})
                def rewrite(target, rename=None, extra=None):
                    with zipfile.ZipFile({str(base)!r}) as src, zipfile.ZipFile(target, "w") as dst:
                        for item in src.infolist():
                            name = rename.get(item.filename, item.filename) if rename else item.filename
                            dst.writestr(name, src.read(item))
                        if extra:
                            dst.writestr(*extra)
                upper = {str(Path(tmp) / "upper.xlsx")!r}
                rewrite(upper, rename={{"xl/worksheets/sheet1.xml": "xl/worksheets/sheet1.XML"}})
                odf = {str(Path(tmp) / "odf.xlsx")!r}
                rewrite(odf, rename={{"xl/worksheets/sheet1.xml": "xl/worksheets/old.bin"}},
                        extra=("content.xml", '<t xmlns:table="urn:t"><c table:formula="of:=WEBSERVICE(&quot;x&quot;)"/></t>'))
                flat = {str(Path(tmp) / "flat.xlsx")!r}
                open(flat, "w").write("<office:document/>")
                print(recalc.network_formula_parts(upper), recalc.network_formula_parts(odf))
                print(recalc.recalc(flat)["error"].startswith("Could not inspect"))
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().splitlines()
            # old.bin continua sendo XML: o nome não importa, o conteúdo é inspecionado.
            self.assertEqual(lines[0], "['xl/worksheets/sheet1.XML'] ['xl/worksheets/old.bin', 'content.xml']")
            self.assertEqual(lines[1], "True")

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

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf não instalado")
    def test_pdf_bounding_box_height_follows_page_rotation(self):
        # Página 600x800 com /Rotate 90 aparece como imagem 800x600: 10 px = 10 pt, menos que a fonte de 12.
        with tempfile.TemporaryDirectory() as tmp:
            from pypdf import PdfWriter
            writer = PdfWriter()
            writer.add_blank_page(600, 800).rotate(90)
            pdf = Path(tmp) / "rot.pdf"
            with open(pdf, "wb") as fh:
                writer.write(fh)
            fields = Path(tmp) / "fields.json"
            fields.write_text(json.dumps({
                "pages": [{"page_number": 1, "image_width": 800, "image_height": 600}],
                "form_fields": [{"page_number": 1, "description": "nome",
                                 "label_bounding_box": [0, 0, 50, 10], "entry_bounding_box": [60, 0, 300, 10],
                                 "entry_text": {"text": "x", "font_size": 12}}]}))
            result = subprocess.run([sys.executable, str(SKILLS / "pdf/scripts/check_bounding_boxes.py"),
                                     str(fields), str(pdf)], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("FAILURE: entry bounding box height (10.0)", result.stdout)

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

    def test_pdf_annotations_follow_page_rotation(self):
        from pypdf import PdfReader, PdfWriter
        with tempfile.TemporaryDirectory() as tmp:
            src, out, fields = (Path(tmp) / n for n in ("rot.pdf", "out.pdf", "fields.json"))
            w = PdfWriter()
            w.add_blank_page(600, 800).rotation = 90  # exibida como 800x600
            with open(src, "wb") as f:
                w.write(f)
            fields.write_text(json.dumps({
                "pages": [{"page_number": 1, "image_width": 800, "image_height": 600}],
                "form_fields": [{"page_number": 1, "entry_bounding_box": [100, 100, 200, 120],
                                 "entry_text": {"text": "Smith", "font_size": 10}}]}))
            result = run_in(SKILLS / "pdf/scripts", f"""
                from fill_pdf_form_with_annotations import fill_pdf_form
                fill_pdf_form({str(src)!r}, {str(fields)!r}, {str(out)!r})
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = PdfReader(out).pages[0]
            self.assertEqual(page.rotation % 360, 0)
            rect = [float(v) for v in page["/Annots"][0].get_object()["/Rect"]]
            # Na página exibida (800x600): x 100-200, y 100-120 a partir do topo -> 480-500 a partir da base.
            self.assertEqual(rect, [100.0, 480.0, 200.0, 500.0])

    def test_pdf_annotations_follow_mediabox_origin(self):
        # MediaBox [100 200 700 1000]: a caixa [10 10 110 30] da imagem 600x800 vai para (110, 970, 210, 990).
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import RectangleObject
        with tempfile.TemporaryDirectory() as tmp:
            src, out, fields = (Path(tmp) / n for n in ("off.pdf", "out.pdf", "fields.json"))
            w = PdfWriter()
            w.add_blank_page(600, 800).mediabox = RectangleObject([100, 200, 700, 1000])
            with open(src, "wb") as f:
                w.write(f)
            fields.write_text(json.dumps({
                "pages": [{"page_number": 1, "image_width": 600, "image_height": 800}],
                "form_fields": [{"page_number": 1, "entry_bounding_box": [10, 10, 110, 30],
                                 "entry_text": {"text": "Smith", "font_size": 10}}]}))
            result = run_in(SKILLS / "pdf/scripts", f"""
                from fill_pdf_form_with_annotations import fill_pdf_form
                fill_pdf_form({str(src)!r}, {str(fields)!r}, {str(out)!r})
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            rect = [float(v) for v in PdfReader(out).pages[0]["/Annots"][0].get_object()["/Rect"]]
            self.assertEqual(rect, [110.0, 970.0, 210.0, 990.0])

    def test_pdf_fill_updates_widgets_on_every_page(self):
        # customer_name tem widgets nas páginas 1 e 2; os dois precisam receber a aparência do valor.
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, TextStringObject
        with tempfile.TemporaryDirectory() as tmp:
            src, out, fields = (Path(tmp) / n for n in ("form.pdf", "out.pdf", "fields.json"))
            w = PdfWriter()
            pages = [w.add_blank_page(300, 300), w.add_blank_page(300, 300)]
            field = DictionaryObject({NameObject("/FT"): NameObject("/Tx"),
                                      NameObject("/T"): TextStringObject("customer_name")})
            field_ref = w._add_object(field)
            kids = ArrayObject()
            for page in pages:
                widget = DictionaryObject({
                    NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Widget"),
                    NameObject("/Rect"): ArrayObject([FloatObject(v) for v in (10, 10, 200, 30)]),
                    NameObject("/Parent"): field_ref, NameObject("/P"): page.indirect_reference,
                    NameObject("/DA"): TextStringObject("/Helv 10 Tf 0 g")})
                ref = w._add_object(widget)
                kids.append(ref)
                page[NameObject("/Annots")] = ArrayObject([ref])
            field[NameObject("/Kids")] = kids
            w._root_object[NameObject("/AcroForm")] = DictionaryObject({
                NameObject("/Fields"): ArrayObject([field_ref]), NameObject("/DA"): TextStringObject("/Helv 10 Tf 0 g")})
            with open(src, "wb") as f:
                w.write(f)
            fields.write_text(json.dumps([{"field_id": "customer_name", "page": 2, "value": "Ana"}]))
            result = run_in(SKILLS / "pdf/scripts", f"""
                from fill_fillable_fields import fill_pdf_fields
                fill_pdf_fields({str(src)!r}, {str(fields)!r}, {str(out)!r})
            """)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            widgets = [p["/Annots"][0].get_object() for p in PdfReader(out).pages]
            self.assertEqual([("/AP" in wd) for wd in widgets], [True, True])

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
                d = seen["duration"]
                total = sum(d) if isinstance(d, list) else d * info["frame_count"]
                print(round(total), info["duration_seconds"])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines()[-1].split(), ["2000", "2.0"])

    def test_removing_duplicate_frames_keeps_their_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_in(SKILLS / "slack-gif-creator", f"""
                import sys, types
                seen = {{}}
                def imwrite(path, frames, duration, loop):
                    seen["duration"] = duration
                    open(path, "wb").write(b"gif")
                sys.modules["imageio"] = types.ModuleType("imageio")
                sys.modules["imageio.v3"] = types.SimpleNamespace(imwrite=imwrite)
                import numpy as np
                from core.gif_builder import GIFBuilder
                b = GIFBuilder(64, 64, fps=10)
                for value in [0] * 10 + [255] * 10:  # duas poses de 1 s cada
                    b.add_frame(np.full((64, 64, 3), value, dtype=np.uint8))
                info = b.save({str(Path(tmp) / "d.gif")!r}, remove_duplicates=True)
                print(seen["duration"], info["duration_seconds"])
            """)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines()[-1], "[1000.0, 1000.0] 2.0")


def _running(pid):
    """Vivo e não zumbi: num contêiner cujo PID 1 não recolhe órfãos, o filho morto fica em estado Z."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True  # sem /proc (macOS): o launchd recolhe o processo


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
                if not _running(pid):
                    break
                time.sleep(0.1)
            else:
                os.kill(pid, 9)
                self.fail("o filho que ignora SIGTERM continuou vivo")

    def test_occupied_port_is_rejected_before_running_the_command(self):
        with socket.socket() as busy, tempfile.TemporaryDirectory() as tmp:
            busy.bind(("127.0.0.1", 0))
            busy.listen()
            port = busy.getsockname()[1]
            marker = Path(tmp) / "ran"
            server = f"{sys.executable} -m http.server {port} --bind 127.0.0.1"
            result = subprocess.run([sys.executable, str(SKILLS / "webapp-testing/scripts/with_server.py"),
                                     "--server", server, "--port", str(port), "--timeout", "10", "--",
                                     sys.executable, "-c", f"open({str(marker)!r}, 'w')"],
                                    capture_output=True, text=True, timeout=60)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("already in use", result.stderr)
            self.assertFalse(marker.exists())

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
