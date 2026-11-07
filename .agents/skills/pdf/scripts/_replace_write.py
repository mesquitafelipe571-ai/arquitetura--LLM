"""Read inputs and write outputs without following a link planted at their paths."""

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def replacing(path):
    """Yield a temp path beside `path` (same suffix, so image libraries keep the format); on
    success it replaces `path`, so a symlink there is swapped out instead of written through."""
    path = Path(path)
    refuse_linked_input(path.parent, "output folder")  # os.replace swaps a link at path, not one above it
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=path.suffix, dir=path.parent)
    os.close(fd)
    try:
        yield tmp
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def refuse_linked_input(path, what="input"):
    """A linked input (or a folder above it) would copy a private local file into the output; a
    linked output folder would make the write land outside the workspace."""
    # Lexical, not abspath(): in "link/../x" the write still goes through "link".
    path = Path(os.getcwd(), path)
    cwd = Path(os.getcwd())
    # Inside the working directory the user picked the root; elsewhere every folder counts except
    # top-level ones, which only an admin creates (macOS /tmp and /var are links).
    stop = cwd if Path(os.path.abspath(path)).is_relative_to(cwd) else None
    for p in (path, *path.parents):
        if p == stop or len(p.parts) <= 2:
            break
        if p.is_symlink():
            raise ValueError(f"{what} goes through a symlink: {p}")
