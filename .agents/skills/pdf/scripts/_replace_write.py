"""Write an output file without following a link planted at its path."""

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
