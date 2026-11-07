"""Shared utilities for skill-creator scripts."""

import os
import tempfile
from pathlib import Path


def refuse_linked_folder(folder, what: str = "output folder") -> None:
    """os.replace swaps a link planted at an output file, but a linked folder at or above it would
    still make the write land outside the workspace."""
    path = Path(os.path.abspath(folder))
    cwd = Path(os.getcwd())
    # Inside the working directory the user picked the root; elsewhere every folder counts except
    # top-level ones, which only an admin creates (macOS /tmp and /var are links).
    stop = cwd if path.is_relative_to(cwd) else None
    for p in (path, *path.parents):
        if p == stop or len(p.parts) <= 2:
            break
        if p.is_symlink():
            raise ValueError(f"{what} goes through a symlink: {p}")


def read_text_no_links(path, what: str = "input file") -> str:
    """Inputs from a third-party workspace: a linked file (or folder above it) would send a
    private local file on to `claude -p` or into a report."""
    refuse_linked_folder(path, what)
    return Path(path).read_text()


def write_text_replace(path: Path, text: str) -> None:
    """Write to a temp file beside path and move it into place: a link planted at path (e.g. in a
    workspace from a third party) is replaced, never followed to overwrite its target."""
    path = Path(path)
    refuse_linked_folder(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise



def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content)."""
    # The content goes to `claude -p`: a linked SKILL.md, skill folder or parent would send a private one.
    refuse_linked_folder(Path(skill_path) / "SKILL.md", "SKILL.md")
    content = (Path(skill_path) / "SKILL.md").read_text()
    lines = content.split("\n")

    if lines[0].strip() != "---":
        raise ValueError("SKILL.md missing frontmatter (no opening ---)")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("SKILL.md missing frontmatter (no closing ---)")

    name = ""
    description = ""
    frontmatter_lines = lines[1:end_idx]
    i = 0
    while i < len(frontmatter_lines):
        line = frontmatter_lines[i]
        if line.startswith("name:"):
            name = line[len("name:"):].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            value = line[len("description:"):].strip()
            # Handle YAML multiline indicators (>, |, >-, |-)
            if value in (">", "|", ">-", "|-"):
                continuation_lines: list[str] = []
                i += 1
                # Blank lines separate paragraphs inside the block; the block ends at the next unindented key.
                while i < len(frontmatter_lines) and (
                    frontmatter_lines[i].startswith(("  ", "\t")) or not frontmatter_lines[i].strip()
                ):
                    continuation_lines.append(frontmatter_lines[i].strip())
                    i += 1
                description = " ".join(line for line in continuation_lines if line)
                continue
            else:
                description = value.strip('"').strip("'")
        i += 1

    return name, description, content
