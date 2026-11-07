"""Add comments to a DOCX document.

Accepts either an unpacked directory OR a .docx/.dotx file directly.

Usage:
    # Against an unpacked directory (writes satellite files in place)
    python comment.py unpacked/ "Comment text"
    python comment.py unpacked/ "Reply text" --parent 0

    # Against a .docx directly (extracts, writes satellite files, rezips)
    python comment.py contract.docx "This cap is too low" -o annotated.docx
    python comment.py contract.docx "Comment" --id 5      # explicit ID

The comment ID is auto-assigned (max existing + 1) unless --id is given.
Plain text is XML-escaped automatically; if you pass already-escaped text
(e.g. &amp;, &#x2019;) use --raw to skip escaping.

After running, add markers to word/document.xml so the comment is visible:
  <w:commentRangeStart w:id="N"/>
  ... commented content ...
  <w:commentRangeEnd w:id="N"/>
  <w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="N"/></w:r>
"""

import argparse
import os
import random
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import defusedxml.minidom
from xml.parsers.expat import ExpatError
from xml.sax.saxutils import escape as xml_escape

from office.helpers import opc_target, rezip as _rezip, safe_extract as _safe_extract

TEMPLATE_DIR = Path(__file__).parent / "templates"
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "w16cid": "http://schemas.microsoft.com/office/word/2016/wordml/cid",
    "w16cex": "http://schemas.microsoft.com/office/word/2018/wordml/cex",
}

COMMENT_XML = """\
<w:comment w:id="{id}" w:author="{author}" w:date="{date}" w:initials="{initials}">
  <w:p w14:paraId="{para_id}" w14:textId="77777777">
    <w:r>
      <w:rPr><w:rStyle w:val="CommentReference"/></w:rPr>
      <w:annotationRef/>
    </w:r>
    <w:r>
      <w:rPr>
        <w:color w:val="000000"/>
        <w:sz w:val="20"/>
        <w:szCs w:val="20"/>
      </w:rPr>
      <w:t xml:space="preserve">{text}</w:t>
    </w:r>
  </w:p>
</w:comment>"""

COMMENT_MARKER_TEMPLATE = """
Add to word/document.xml (markers must be direct children of w:p, never inside w:r):
  <w:commentRangeStart w:id="{cid}"/>
  <w:r>...</w:r>
  <w:commentRangeEnd w:id="{cid}"/>
  <w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="{cid}"/></w:r>"""

REPLY_MARKER_TEMPLATE = """
Nest markers inside parent {pid}'s markers (direct children of w:p, never inside w:r):
  <w:commentRangeStart w:id="{pid}"/><w:commentRangeStart w:id="{cid}"/>
  <w:r>...</w:r>
  <w:commentRangeEnd w:id="{cid}"/><w:commentRangeEnd w:id="{pid}"/>
  <w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="{pid}"/></w:r>
  <w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="{cid}"/></w:r>"""

SMART_QUOTE_ENTITIES = {
    "“": "&#x201C;",
    "”": "&#x201D;",
    "‘": "&#x2018;",
    "’": "&#x2019;",
}


def _generate_hex_id() -> str:
    return f"{random.randint(0, 0x7FFFFFFE):08X}"


def _encode_smart_quotes(text: str) -> str:
    for char, entity in SMART_QUOTE_ENTITIES.items():
        text = text.replace(char, entity)
    return text


def _append_xml(xml_path: Path, root_tag: str, content: str) -> None:
    dom = defusedxml.minidom.parseString(xml_path.read_text(encoding="utf-8"))
    prefix, local = root_tag.split(":")
    root = dom.getElementsByTagNameNS(NS[prefix], local)[0]  # by namespace: any prefix in the file
    # The imported nodes use these prefixes; declare any the existing part lacks.
    for prefix, uri in NS.items():
        if not root.hasAttribute(f"xmlns:{prefix}"):
            root.setAttribute(f"xmlns:{prefix}", uri)
    ns_attrs = " ".join(f'xmlns:{k}="{v}"' for k, v in NS.items())
    wrapper_dom = defusedxml.minidom.parseString(f"<root {ns_attrs}>{content}</root>")
    for child in wrapper_dom.documentElement.childNodes:  
        if child.nodeType == child.ELEMENT_NODE:
            root.appendChild(dom.importNode(child, True))
    output = _encode_smart_quotes(dom.toxml(encoding="UTF-8").decode("utf-8"))
    xml_path.write_text(output, encoding="utf-8")


def _find_para_id(comments_path: Path, comment_id: int) -> tuple[str | None, bool]:
    """(paraId of the comment, assigned_now). w14:paraId is optional in WordprocessingML: a comment
    without one gets one on its last paragraph, so a reply can point at it."""
    dom = defusedxml.minidom.parseString(comments_path.read_text(encoding="utf-8"))
    for c in dom.getElementsByTagNameNS(NS["w"], "comment"):
        if c.getAttributeNS(NS["w"], "id") == str(comment_id):
            paragraphs = c.getElementsByTagNameNS(NS["w"], "p")
            if not paragraphs:
                return None, False
            # commentsExtended links a comment by the paraId of its last paragraph.
            if pid := paragraphs[-1].getAttributeNS(NS["w14"], "paraId"):
                return pid, False
            pid = _generate_hex_id()
            root = dom.documentElement
            if not root.hasAttribute("xmlns:w14"):
                root.setAttribute("xmlns:w14", NS["w14"])
            paragraphs[-1].setAttributeNS(NS["w14"], "w14:paraId", pid)
            comments_path.write_text(
                _encode_smart_quotes(dom.toxml(encoding="UTF-8").decode("utf-8")), encoding="utf-8"
            )
            return pid, True
    return None, False


def _has_comment_ex(ext_path: Path, para_id: str) -> bool:
    dom = defusedxml.minidom.parseString(ext_path.read_text(encoding="utf-8"))
    return any(e.getAttributeNS(NS["w15"], "paraId") == para_id
               for e in dom.getElementsByTagNameNS(NS["w15"], "commentEx"))


def _comment_ids(comments_path: Path) -> list[str]:
    if not comments_path.exists():
        return []
    dom = defusedxml.minidom.parseString(comments_path.read_text(encoding="utf-8"))
    return [c.getAttributeNS(NS["w"], "id") for c in dom.getElementsByTagNameNS(NS["w"], "comment")]


def _next_comment_id(comments_path: Path) -> int:
    ids = [int(i) for i in _comment_ids(comments_path) if i.lstrip("-").isdigit()]
    return (max(ids) + 1) if ids else 0


def _get_next_rid(rels_path: Path) -> int:
    dom = defusedxml.minidom.parseString(rels_path.read_text(encoding="utf-8"))
    max_rid = 0
    for rel in dom.getElementsByTagNameNS("*", "Relationship"):
        rid = rel.getAttribute("Id")
        if rid and rid.startswith("rId"):
            try:
                max_rid = max(max_rid, int(rid[3:]))
            except ValueError:
                pass
    return max_rid + 1


def _has_relationship(rels_path: Path, target: str) -> bool:
    dom = defusedxml.minidom.parseString(rels_path.read_text(encoding="utf-8"))
    return any(
        rel.getAttribute("Target") == target
        for rel in dom.getElementsByTagNameNS("*", "Relationship")
    )


def _child_like_root(dom, local_name: str):
    """New child element in the root's namespace and with its prefix (e.g. `pkg:Relationship`)."""
    root = dom.documentElement
    name = f"{root.prefix}:{local_name}" if root.prefix else local_name
    return dom.createElementNS(root.namespaceURI, name)


def _has_content_type(ct_path: Path, part_name: str) -> bool:
    dom = defusedxml.minidom.parseString(ct_path.read_text(encoding="utf-8"))
    return any(
        o.getAttribute("PartName") == part_name
        for o in dom.getElementsByTagNameNS("*", "Override")
    )


_COMMENT_RELS = [
    ("http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments", "comments.xml",
     "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"),
    ("http://schemas.microsoft.com/office/2011/relationships/commentsExtended", "commentsExtended.xml",
     "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml"),
    ("http://schemas.microsoft.com/office/2016/09/relationships/commentsIds", "commentsIds.xml",
     "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsIds+xml"),
    ("http://schemas.microsoft.com/office/2018/08/relationships/commentsExtensible", "commentsExtensible.xml",
     "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtensible+xml"),
]


def _rels_path(unpacked_dir: Path) -> Path:
    return unpacked_dir / "word" / "_rels" / "document.xml.rels"


def _linked_comment_parts(unpacked_dir: Path) -> dict[str, str]:
    """Parts already linked from document.xml per comment relationship type (e.g. word/comments1.xml)."""
    rels_path = _rels_path(unpacked_dir)
    if not rels_path.exists():
        return {}
    comment_types = {rel_type for rel_type, _, _ in _COMMENT_RELS}
    linked: dict[str, str] = {}
    dom = defusedxml.minidom.parseString(rels_path.read_text(encoding="utf-8"))
    for rel in dom.getElementsByTagNameNS("*", "Relationship"):
        rel_type = rel.getAttribute("Type")
        if rel_type not in comment_types or rel_type in linked:
            continue
        part = opc_target(rel.getAttribute("Target"), "word/document.xml", rel.getAttribute("TargetMode"))
        if part is not None:
            linked[rel_type] = part
    return linked


def _comment_parts(unpacked_dir: Path) -> dict[str, str]:
    """Part each comment relationship uses: the linked one, else word/<default name>."""
    linked = _linked_comment_parts(unpacked_dir)
    return {rel_type: linked.get(rel_type, f"word/{name}") for rel_type, name, _ in _COMMENT_RELS}


def _ensure_comment_relationships(unpacked_dir: Path) -> None:
    rels_path = _rels_path(unpacked_dir)
    if not rels_path.exists():
        # A minimal document may have no relationships yet; the comment parts still need one.
        rels_path.parent.mkdir(parents=True, exist_ok=True)
        rels_path.write_text(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
            encoding="utf-8",
        )
    linked = _linked_comment_parts(unpacked_dir)
    dom = defusedxml.minidom.parseString(rels_path.read_text(encoding="utf-8"))
    root = dom.documentElement
    next_rid = _get_next_rid(rels_path)
    changed = False
    for rel_type, target, _ in _COMMENT_RELS:
        if rel_type in linked:
            continue
        rel = _child_like_root(dom, "Relationship")
        rel.setAttribute("Id", f"rId{next_rid}")
        rel.setAttribute("Type", rel_type)
        rel.setAttribute("Target", target)
        root.appendChild(rel)
        next_rid += 1
        changed = True
    if changed:
        rels_path.write_bytes(dom.toxml(encoding="UTF-8"))


def _ensure_comment_content_types(unpacked_dir: Path) -> None:
    ct_path = unpacked_dir / "[Content_Types].xml"
    if not ct_path.exists():
        return
    parts = _comment_parts(unpacked_dir)
    dom = defusedxml.minidom.parseString(ct_path.read_text(encoding="utf-8"))
    root = dom.documentElement
    existing = {
        o.getAttribute("PartName")
        for o in dom.getElementsByTagNameNS("*", "Override")
    }
    changed = False
    for rel_type, _, content_type in _COMMENT_RELS:
        part_name = "/" + parts[rel_type]
        if part_name in existing:
            continue
        override = _child_like_root(dom, "Override")
        override.setAttribute("PartName", part_name)
        override.setAttribute("ContentType", content_type)
        root.appendChild(override)
        changed = True
    if changed:
        ct_path.write_bytes(dom.toxml(encoding="UTF-8"))


def _refuse_linked_writes(unpacked_dir: Path, *parts: Path) -> None:
    """Checked before the first write: a link at a part, or at a folder between it and the
    package root, would make the edit land outside the package."""
    root = Path(os.path.abspath(unpacked_dir))
    for part in parts:
        for p in (Path(os.path.abspath(part)), *Path(os.path.abspath(part)).parents):
            if p == root:
                break
            if p.is_symlink():
                raise ValueError(f"refusing to write through a symlink: {p}")


def add_comment(
    unpacked_dir: Path | str,
    text: str,
    comment_id: int | None = None,
    author: str = "Claude",
    initials: str = "C",
    parent_id: int | None = None,
    raw: bool = False,
) -> tuple[int, str, str]:
    unpacked_dir = Path(unpacked_dir)
    if not raw:
        text = xml_escape(text)
    author = xml_escape(author, {'"': "&quot;"})
    initials = xml_escape(initials, {'"': "&quot;"})
    word = unpacked_dir / "word"
    if not word.exists():
        raise FileNotFoundError(f"{word} not found (not an unpacked .docx?)")

    # Reuse the parts the document already links (e.g. word/comments1.xml), so IDs and parents match.
    comments, ext, ids, extensible = (
        unpacked_dir / part for part in _comment_parts(unpacked_dir).values()
    )
    _refuse_linked_writes(unpacked_dir, comments, ext, ids, extensible,
                          _rels_path(unpacked_dir), unpacked_dir / "[Content_Types].xml")
    if comment_id is None:
        comment_id = _next_comment_id(comments)
    elif str(comment_id) in _comment_ids(comments):
        # w:id must be unique: a second comment with it would make the document markers ambiguous.
        raise ValueError(f"comment id {comment_id} is already used")

    parent_para = None
    if parent_id is not None:
        if comments.exists():
            parent_para, _ = _find_para_id(comments, parent_id)
        if not parent_para:
            raise ValueError(f"parent comment {parent_id} not found")

    para_id, durable_id = _generate_hex_id(), _generate_hex_id()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not comments.exists():
        shutil.copy(TEMPLATE_DIR / "comments.xml", comments)
    _ensure_comment_relationships(unpacked_dir)
    _ensure_comment_content_types(unpacked_dir)
    _append_xml(
        comments,
        "w:comments",
        COMMENT_XML.format(
            id=comment_id, author=author, date=ts, initials=initials,
            para_id=para_id, text=text,
        ),
    )

    if not ext.exists():
        shutil.copy(TEMPLATE_DIR / "commentsExtended.xml", ext)
    if parent_para is not None and not _has_comment_ex(ext, parent_para):
        # The reply points at the parent's commentEx: register it when missing (new paraId or not).
        _append_xml(ext, "w15:commentsEx", f'<w15:commentEx w15:paraId="{parent_para}" w15:done="0"/>')
    if parent_para is not None:
        _append_xml(
            ext, "w15:commentsEx",
            f'<w15:commentEx w15:paraId="{para_id}" w15:paraIdParent="{parent_para}" w15:done="0"/>',
        )
    else:
        _append_xml(
            ext, "w15:commentsEx",
            f'<w15:commentEx w15:paraId="{para_id}" w15:done="0"/>',
        )

    if not ids.exists():
        shutil.copy(TEMPLATE_DIR / "commentsIds.xml", ids)
    _append_xml(
        ids, "w16cid:commentsIds",
        f'<w16cid:commentId w16cid:paraId="{para_id}" w16cid:durableId="{durable_id}"/>',
    )

    if not extensible.exists():
        shutil.copy(TEMPLATE_DIR / "commentsExtensible.xml", extensible)
    _append_xml(
        extensible, "w16cex:commentsExtensible",
        f'<w16cex:commentExtensible w16cex:durableId="{durable_id}" w16cex:dateUtc="{ts}"/>',
    )

    action = "reply" if parent_id is not None else "comment"
    return comment_id, para_id, f"Added {action} id={comment_id} (paraId={para_id})"


def main() -> None:
    p = argparse.ArgumentParser(description="Add a comment to a DOCX (directory or .docx file).")
    p.add_argument("input", help="Unpacked DOCX directory OR a .docx/.dotx file")
    p.add_argument("text", help="Comment text (plain text; XML-escaped automatically)")
    p.add_argument("--raw", action="store_true",
                   help="Treat text as pre-escaped XML (skip automatic escaping)")
    p.add_argument("--id", type=int, dest="comment_id",
                   help="Comment ID (default: auto-assign as max existing + 1)")
    p.add_argument("--author", default="Claude", help="Author name")
    p.add_argument("--initials", default="C", help="Author initials")
    p.add_argument("--parent", type=int, help="Parent comment ID (makes this a reply)")
    p.add_argument("-o", "--output",
                   help="Output .docx path (only used when input is a .docx; default: overwrite input)")
    args = p.parse_args()

    src = Path(args.input)

    try:
        if src.is_dir():
            if args.output:
                print("Warning: --output ignored for directory input", file=sys.stderr)
            cid, _, msg = add_comment(
                src, args.text, comment_id=args.comment_id,
                author=args.author, initials=args.initials,
                parent_id=args.parent, raw=args.raw,
            )
            print(msg)
        elif src.is_file() and src.suffix.lower() in (".docx", ".dotx"):
            out = Path(args.output) if args.output else src
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                with zipfile.ZipFile(src) as zf:
                    _safe_extract(zf, tmp_path)
                cid, _, msg = add_comment(
                    tmp_path, args.text, comment_id=args.comment_id,
                    author=args.author, initials=args.initials,
                    parent_id=args.parent, raw=args.raw,
                )
                _rezip(tmp_path, out)
            print(msg)
            print(f"Wrote {out} (comment defined; add markers to word/document.xml to make it visible)")
        else:
            print(f"Error: {src} is neither a directory nor a .docx/.dotx file", file=sys.stderr)
            sys.exit(1)
    except (FileNotFoundError, ValueError, zipfile.BadZipFile, ExpatError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.parent is not None:
        print(REPLY_MARKER_TEMPLATE.format(pid=args.parent, cid=cid))
    else:
        print(COMMENT_MARKER_TEMPLATE.format(cid=cid))


if __name__ == "__main__":
    main()
