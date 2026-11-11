"""The .env file is actually read, and the shell still wins over it.

Covers BUG-0004: the README instructed `Copy-Item .env.example .env`, but the
application was configured with `env_file=None` and silently ignored the file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import (
    ENV_FILE_OVERRIDE_VAR,
    Settings,
    get_settings,
    reset_settings_cache,
    resolve_env_file,
)


@pytest.fixture
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated .env, with the settings cache cleared around the test."""
    path = tmp_path / ".env"
    monkeypatch.setenv(ENV_FILE_OVERRIDE_VAR, str(path))
    for key in ("DEMO_MODE", "PAYPAL_MODE", "PAYPAL_BASE_URL", "LLM_PROVIDER"):
        monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
    yield path
    reset_settings_cache()


def test_values_are_read_from_the_env_file(env_file: Path) -> None:
    env_file.write_text("DEMO_MODE=true\nPAYPAL_MODE=mock\nLLM_PROVIDER=gemini\n", encoding="utf-8")

    settings = get_settings()

    assert settings.demo_mode is True
    assert settings.paypal_mode == "mock"
    assert settings.llm_provider == "gemini"


def test_real_environment_overrides_the_env_file(
    env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale .env must never beat what you just exported in the shell."""
    env_file.write_text("DEMO_MODE=false\nPAYPAL_MODE=mock\n", encoding="utf-8")
    monkeypatch.setenv("DEMO_MODE", "true")
    reset_settings_cache()

    settings = get_settings()

    assert settings.demo_mode is True, "the shell value must win"
    assert settings.paypal_mode == "mock", "unset keys still come from .env"


def test_missing_env_file_is_not_an_error(env_file: Path) -> None:
    assert not env_file.exists()
    assert resolve_env_file() is None
    assert get_settings().demo_mode is False


def test_env_file_cannot_enable_a_production_paypal_host(env_file: Path) -> None:
    """Rule R4 survives configuration arriving via .env rather than the shell."""
    env_file.write_text("PAYPAL_BASE_URL=https://api-m.paypal.com\n", encoding="utf-8")
    reset_settings_cache()

    with pytest.raises(ValueError):
        get_settings()


def test_demo_mode_declared_in_env_file_counts_as_explicit(env_file: Path) -> None:
    """No spurious startup warning when DEMO_MODE was set deliberately in .env."""
    env_file.write_text("# a comment\nDEMO_MODE=false\n", encoding="utf-8")
    reset_settings_cache()

    assert get_settings().demo_mode_was_explicit is True


def test_commented_out_demo_mode_does_not_count_as_explicit(env_file: Path) -> None:
    env_file.write_text("#DEMO_MODE=true\nPAYPAL_MODE=mock\n", encoding="utf-8")
    reset_settings_cache()

    settings = get_settings()
    assert settings.demo_mode is False
    assert settings.demo_mode_was_explicit is False, "a commented line is not a choice"


def test_constructing_settings_directly_ignores_any_env_file(env_file: Path) -> None:
    """Settings() stays hermetic; only get_settings() loads the file."""
    env_file.write_text("DEMO_MODE=true\n", encoding="utf-8")

    assert Settings().demo_mode is False
