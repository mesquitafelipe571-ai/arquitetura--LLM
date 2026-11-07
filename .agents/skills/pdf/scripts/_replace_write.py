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
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=path.suffix, dir=path.parent)
    os.close(fd)
    try:
        yield tmp
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def refuse_linked_input(path):
    """A linked input (or a folder above it) would copy a private local file into the output."""
    path = Path(os.path.abspath(path))
    cwd = Path(os.getcwd())
    # shortcut: ancestors outside the working directory are not checked (system temp dirs such as
    # macOS /tmp are links); move the check to an explicit root if callers read from elsewhere.
    for p in (path, *path.parents):
        if p is not path and (p == cwd or not p.is_relative_to(cwd)):
            break
        if p.is_symlink():
            raise ValueError(f"input goes through a symlink: {p}")
