"""SQLite URL parsing, including Windows drive-letter paths.

These tests run on Linux CI but exercise Windows path strings, because the
project owner runs on Windows 11 and ``sqlite:///C:/Users/...`` is the form
the Playwright run and the PowerShell helper produce.

They are pure string tests - nothing touches the filesystem - so a
``C:\\Users\\...`` string cannot accidentally create a directory called ``C:``
in the repository when the suite runs on Linux.
"""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

import pytest

from app.db.sqlite_url import (
    is_sqlite_url,
    looks_like_windows_absolute,
    sqlite_file_path,
    sqlite_url_from_path,
)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # Windows, forward slashes - what sqlite_url_from_path emits.
        ("sqlite:///C:/Users/Shorya/dev/app.sqlite3", "C:/Users/Shorya/dev/app.sqlite3"),
        # Windows, a username containing a space.
        (
            "sqlite:///C:/Users/Test User/merchantshield/app.sqlite3",
            "C:/Users/Test User/merchantshield/app.sqlite3",
        ),
        # Windows, raw backslashes - SQLAlchemy accepts these too.
        (r"sqlite:///C:\Users\Test User\app.sqlite3", r"C:\Users\Test User\app.sqlite3"),
        # Lower-case drive letter.
        ("sqlite:///d:/data/app.db", "d:/data/app.db"),
        # POSIX absolute (four slashes) and relative (three).
        ("sqlite:////var/lib/merchantshield/app.db", "/var/lib/merchantshield/app.db"),
        ("sqlite:///./merchantshield.db", "./merchantshield.db"),
        ("sqlite:///merchantshield.db", "merchantshield.db"),
        ("sqlite:///artifacts/phase-0/local-windows/e2e.sqlite3",
         "artifacts/phase-0/local-windows/e2e.sqlite3"),
    ],
)
def test_file_path_is_extracted(url: str, expected: str) -> None:
    assert sqlite_file_path(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite:///file:x?mode=memory&cache=shared",
        "postgresql+psycopg://user:pw@localhost/db",
        "mysql://root@localhost/db",
    ],
)
def test_urls_without_a_real_file_return_none(url: str) -> None:
    assert sqlite_file_path(url) is None


def test_is_sqlite_url() -> None:
    assert is_sqlite_url("sqlite:///x.db")
    assert is_sqlite_url("sqlite://")
    assert not is_sqlite_url("postgresql://host/db")


# --------------------------------------------------------------------------
# Building
# --------------------------------------------------------------------------


def test_url_from_a_simulated_windows_path() -> None:
    """The exact shape the Playwright config and windows_check.ps1 produce."""
    windows_path = PureWindowsPath(
        r"C:\Users\Test User\dev\merchantshield-ai\artifacts\phase-0\local-windows\e2e.sqlite3"
    )

    url = sqlite_url_from_path(windows_path)

    assert url == (
        "sqlite:///C:/Users/Test User/dev/merchantshield-ai/"
        "artifacts/phase-0/local-windows/e2e.sqlite3"
    )
    assert "\\" not in url, "backslashes must be normalised away"
    assert url.startswith("sqlite:///")


def test_round_trip_windows_path() -> None:
    windows_path = PureWindowsPath(r"C:\dev\merchantshield-test\app.sqlite3")

    url = sqlite_url_from_path(windows_path)
    extracted = sqlite_file_path(url)

    assert extracted == "C:/dev/merchantshield-test/app.sqlite3"
    assert looks_like_windows_absolute(extracted)
    # Re-parsing with Windows semantics gives back the original path.
    assert PureWindowsPath(extracted) == windows_path


def test_round_trip_posix_path() -> None:
    posix_path = PurePosixPath("/home/user/merchantshield-ai/artifacts/e2e.sqlite3")

    url = sqlite_url_from_path(posix_path)
    assert url == "sqlite:////home/user/merchantshield-ai/artifacts/e2e.sqlite3"
    assert sqlite_file_path(url) == str(posix_path)


def test_a_path_with_spaces_survives_the_round_trip() -> None:
    url = sqlite_url_from_path(PureWindowsPath(r"C:\Program Files\ms\app.db"))
    assert sqlite_file_path(url) == "C:/Program Files/ms/app.db"


def test_windows_absolute_detection() -> None:
    assert looks_like_windows_absolute("C:/Users/x")
    assert looks_like_windows_absolute(r"C:\Users\x")
    assert looks_like_windows_absolute("z:/x")
    assert not looks_like_windows_absolute("/var/lib/x")
    assert not looks_like_windows_absolute("./relative.db")
