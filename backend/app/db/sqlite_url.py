"""Parsing and building SQLite URLs, including Windows drive-letter paths.

These are deliberately **pure string functions** with no filesystem access, so
Windows forms such as ``sqlite:///C:/Users/Test User/app.sqlite3`` can be unit
tested from Linux CI. Touching the filesystem is the caller's job.

SQLAlchemy's SQLite URL grammar (the part we care about):

===================================== ==========================================
URL                                   Meaning
===================================== ==========================================
``sqlite://``                         in-memory
``sqlite:///:memory:``                in-memory
``sqlite:///relative/path.db``        relative to the current directory
``sqlite:////absolute/posix.db``      absolute POSIX path (note four slashes)
``sqlite:///C:/Users/me/app.db``      absolute Windows path, forward slashes
``sqlite:///C:\\Users\\me\\app.db``     absolute Windows path, backslashes
===================================== ==========================================
"""

from __future__ import annotations

import re
from pathlib import Path, PurePath

__all__ = ["is_sqlite_url", "sqlite_file_path", "sqlite_url_from_path"]

_SQLITE_PREFIX = "sqlite:"

#: e.g. "C:/..." or "c:\..." - a drive letter followed by a colon.
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


def is_sqlite_url(url: str) -> bool:
    return url.startswith(_SQLITE_PREFIX)


def sqlite_file_path(url: str) -> str | None:
    """Return the file path inside a SQLite URL, or ``None``.

    ``None`` means "there is no file to create a directory for": the URL is
    in-memory, or is not a SQLite URL at all.
    """
    if not is_sqlite_url(url):
        return None

    # Strip the scheme and the driver, e.g. "sqlite+pysqlite:///x" -> "///x".
    _, _, remainder = url.partition(":")

    # "sqlite://" (in-memory) leaves exactly "//".
    if remainder in ("", "//"):
        return None

    if not remainder.startswith("///"):
        return None

    raw = remainder[3:]

    # Query parameters, e.g. "?mode=memory&cache=shared".
    path_part, _, query = raw.partition("?")

    if not path_part or path_part == ":memory:":
        return None
    if "mode=memory" in query:
        return None

    return path_part


def sqlite_url_from_path(path: str | PurePath) -> str:
    """Build a SQLite URL for ``path``.

    Backslashes are converted to forward slashes, which SQLAlchemy accepts on
    Windows and which avoids the string being mangled when it travels through
    a shell, an environment variable or a YAML file.

    An absolute POSIX path keeps its leading slash, producing the documented
    four-slash form ``sqlite:////var/data/app.db``.
    """
    text = str(path).replace("\\", "/")
    return f"sqlite:///{text}"


def sqlite_parent_dir(url: str) -> Path | None:
    """Return the directory that must exist before SQLite can open ``url``.

    ``None`` when there is nothing to create (in-memory, non-SQLite, or a bare
    filename in the current directory).

    Note this returns a :class:`pathlib.Path`, so it is interpreted using the
    *running* platform's rules. A Windows path evaluated on Linux is
    meaningless - which is exactly why the parsing above is kept separate and
    is what the Windows unit tests exercise.
    """
    raw = sqlite_file_path(url)
    if raw is None:
        return None

    parent = Path(raw).parent
    if str(parent) in ("", "."):
        return None
    return parent


def looks_like_windows_absolute(raw_path: str) -> bool:
    """True for ``C:/...`` or ``C:\\...``. Used by tests and diagnostics."""
    return bool(_WINDOWS_DRIVE.match(raw_path))
