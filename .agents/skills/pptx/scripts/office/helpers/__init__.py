import os
import posixpath
import re
import stat
import tempfile
import urllib.parse
import zipfile
from pathlib import Path

OOXML_FAMILY = {
    ".docx": "docx",
    ".dotx": "docx",
    ".pptx": "pptx",
    ".potx": "pptx",
    ".xlsx": "xlsx",
    ".xltx": "xlsx",
}

_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")

SLIDE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"

REL_NAMESPACES = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "http://purl.oclc.org/ooxml/officeDocument/relationships",
}


def listed_slide_rids(pres_dom) -> list[str]:
    """r:id of every <sldId>, matched by namespace URI rather than by prefix."""
    rids = []
    for el in pres_dom.getElementsByTagNameNS("*", "sldId"):
        for i in range(el.attributes.length):
            attr = el.attributes.item(i)
            if attr.localName == "id" and attr.namespaceURI in REL_NAMESPACES:
                rids.append(attr.value)
    return rids


def opc_target(target: str, source_part: str, target_mode: str = "") -> str | None:
    if not target:
        return None
    if target_mode.lower() == "external":
        return None
    if _SCHEME_RE.match(target):
        return None

    target = urllib.parse.unquote(target)

    if "\\" in target:
        raise ValueError(f"relationship target is not a POSIX part name: {target!r}")

    if target.startswith("/"):
        joined = target.lstrip("/")
    else:
        joined = posixpath.join(posixpath.dirname(source_part), target)

    parts: list[str] = []
    for segment in posixpath.normpath(joined).split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not parts:
                raise ValueError(f"relationship target escapes the package: {target!r}")
            parts.pop()
        else:
            parts.append(segment)

    if not parts:
        raise ValueError(f"relationship target resolves to nothing: {target!r}")
    return "/".join(parts)


def rels_source_part(rels_file: Path, unpacked_dir: Path) -> str:
    owner_dir = rels_file.parent.parent.relative_to(unpacked_dir)
    return posixpath.join(owner_dir.as_posix(), rels_file.name[: -len(".rels")]).lstrip("./")


def part_text(data: bytes) -> str:
    return data.decode("utf-8", "surrogateescape")


XML_SPACE = " \t\r\n"


def rendered_text(text: str, preserve: bool) -> str:
    return text if preserve else text.strip(XML_SPACE)


# Expansion limits against zip bombs. Declared sizes bound what extract() writes (zipfile stops
# at file_size), so checking them before extracting is enough.
MAX_EXTRACTED_BYTES = 2 * 1024**3
MAX_COMPRESSION_RATIO = 200  # Office XML compresses ~10-30x; only applied to entries over 1 MiB
_RATIO_MIN_BYTES = 1024**2


def check_archive_limits(zf: zipfile.ZipFile) -> None:
    """Refuse a zip bomb before anything is extracted or read from the archive."""
    total = compressed = 0
    for m in zf.infolist():
        total += m.file_size
        compressed += m.compress_size
        if total > MAX_EXTRACTED_BYTES:
            raise ValueError(f"archive expands to more than {MAX_EXTRACTED_BYTES} bytes")
        if m.file_size > _RATIO_MIN_BYTES and m.file_size > MAX_COMPRESSION_RATIO * max(m.compress_size, 1):
            raise ValueError(f"suspicious compression ratio for archive entry: {m.filename!r}")
    # A bomb split into many entries of at most 1 MiB each slips past the per-entry check.
    if total > _RATIO_MIN_BYTES and total > MAX_COMPRESSION_RATIO * max(compressed, 1):
        raise ValueError("suspicious compression ratio for the archive as a whole")


def refuse_linked_path(target: Path, what: str = "extraction destination") -> None:
    """A linked path (or folder above it) points outside the workspace: as a destination it makes
    resolve() trust a directory there; as an input it copies a private file into the output."""
    path = Path(os.path.abspath(target))
    cwd = Path(os.getcwd())
    # Inside the working directory the user picked the root; elsewhere every folder counts except
    # top-level ones, which only an admin creates (macOS /tmp and /var are links).
    stop = cwd if path.is_relative_to(cwd) else None
    for p in (path, *path.parents):
        if p == stop or len(p.parts) <= 2:
            break
        if p.is_symlink():
            raise ValueError(f"{what} goes through a symlink: {p}")


def refuse_links(root: Path) -> None:
    """An extracted package has no links (safe_extract refuses them); one inside an unpacked
    directory would make an in-place edit read and rewrite a file outside the package."""
    for dirpath, dirnames, filenames in os.walk(root):  # followlinks=False: never descends into one
        for name in dirnames + filenames:
            if os.path.islink(os.path.join(dirpath, name)):
                raise ValueError(f"{os.path.join(dirpath, name)} is a symlink; re-extract the package")


def safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    refuse_linked_path(dest)
    # Only what comes from the archive may end up in dest: a pre-existing unpacked/leak.txt
    # link would be dereferenced by a later `zip -Xr` and ship a local file inside the document.
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise ValueError(f"extraction destination must be a new or empty directory: {dest}")
    dest = dest.resolve()
    check_archive_limits(zf)
    members = zf.infolist()
    for m in members:
        if stat.S_ISLNK(m.external_attr >> 16):
            raise ValueError(f"symlink archive entry not allowed: {m.filename!r}")
        target = (dest / m.filename).resolve()
        if not target.is_relative_to(dest):
            raise ValueError(f"unsafe archive entry: {m.filename!r}")
        zf.extract(m, dest)


def rezip(src_dir: Path, out_path: Path) -> None:
    links = sorted(p for p in src_dir.rglob("*") if p.is_symlink())
    if links:
        # A link would be read through and pack a file from outside the tree into the document.
        raise ValueError(f"refusing to pack symlinks: {', '.join(str(p.relative_to(src_dir)) for p in links)}")
    files = sorted(p for p in src_dir.rglob("*") if p.is_file())
    ct = src_dir / "[Content_Types].xml"
    # The output itself may be a link (os.replace swaps it out); a linked folder above it may not.
    refuse_linked_path(out_path.parent, "output folder")
    fd, tmp_name = tempfile.mkstemp(
        prefix=out_path.name + ".", suffix=".tmp", dir=out_path.parent
    )
    tmp_out = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            with zipfile.ZipFile(fh, "w", zipfile.ZIP_DEFLATED) as zf:
                if ct.exists():
                    zf.write(ct, ct.relative_to(src_dir), compress_type=zipfile.ZIP_STORED)
                for f in files:
                    if f == ct:
                        continue
                    zf.write(f, f.relative_to(src_dir))
        if out_path.exists():
            mode = out_path.stat().st_mode & 0o777
        else:
            umask = os.umask(0)
            os.umask(umask)
            mode = 0o666 & ~umask
        os.chmod(tmp_out, mode)
        os.replace(tmp_out, out_path)
    finally:
        if tmp_out.exists():
            tmp_out.unlink()
