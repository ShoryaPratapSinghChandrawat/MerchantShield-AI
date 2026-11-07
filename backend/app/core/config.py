"""Application configuration.

Hard rules enforced here:

* **R4 - PayPal Sandbox only.** ``validate_paypal_base_url`` rejects every
  PayPal production hostname at startup, even if someone sets it by mistake.
  There is no configuration flag that can re-enable production.
* **R10 - no secrets in code.** Secrets only ever arrive through environment
  variables, and ``safe_dump`` is the only approved way to log configuration.
* ``DEMO_MODE`` unset is treated as ``false`` *and* raises a startup warning,
  so a silent default can never be mistaken for an explicit choice.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

#: backend/app/core/config.py -> core -> app -> backend -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[3]

#: Name of the env var that relocates the dotenv file. Tests point this at a
#: path that does not exist, so a developer's real .env can never leak into a
#: test run.
ENV_FILE_OVERRIDE_VAR = "MS_ENV_FILE"


def resolve_env_file() -> Path | None:
    """Return the .env file to load, or None when there is none.

    Precedence inside pydantic-settings is: real environment variables first,
    then this file. So exporting DEMO_MODE in PowerShell always wins over a
    stale value left in .env.
    """
    override = os.environ.get(ENV_FILE_OVERRIDE_VAR)
    if override is not None:
        candidate = Path(override)
        return candidate if candidate.is_file() else None

    default = REPO_ROOT / ".env"
    return default if default.is_file() else None


def _dotenv_defines(key: str, env_file: Path | None) -> bool:
    """True when ``key`` is assigned in ``env_file`` (comments ignored)."""
    if env_file is None or not env_file.is_file():
        return False
    try:
        text = env_file.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip().removeprefix("export ").strip()
        if name.upper() == key.upper():
            return True
    return False

#: The documented PayPal Sandbox REST host.
#: Source: https://developer.paypal.com/api/orders/v2  ("Base URL(s)")
DEFAULT_PAYPAL_SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"

#: Hostnames that are allowed in addition to ``*.sandbox.paypal.com``.
#: Only loopback hosts, so tests can point the client at a local stub server.
_ALLOWED_NON_PAYPAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "testserver"})

PayPalMode = Literal["auto", "sandbox", "mock"]
LlmProvider = Literal["gemini", "anthropic", "openai", "none"]


class ProductionPayPalHostError(ValueError):
    """Raised when configuration points at a PayPal production endpoint."""


def validate_paypal_base_url(raw: str) -> str:
    """Return ``raw`` unchanged if it is a safe Sandbox/loopback base URL.

    Raises :class:`ProductionPayPalHostError` otherwise. The check is
    allowlist-shaped on purpose: anything that *looks* like PayPal but is not
    explicitly a sandbox host is refused, rather than trying to enumerate every
    production hostname.
    """
    candidate = (raw or "").strip().rstrip("/")
    if not candidate:
        raise ProductionPayPalHostError("PAYPAL_BASE_URL must not be empty.")

    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ProductionPayPalHostError(
            f"PAYPAL_BASE_URL must be an http(s) URL, got {candidate!r}."
        )

    host = (parsed.hostname or "").lower()
    if not host:
        raise ProductionPayPalHostError(f"PAYPAL_BASE_URL has no hostname: {candidate!r}.")

    if host in _ALLOWED_NON_PAYPAL_HOSTS:
        return candidate

    if host == "api-m.sandbox.paypal.com" or host.endswith(".sandbox.paypal.com"):
        return candidate

    raise ProductionPayPalHostError(
        f"Refusing to start: {host!r} is not a PayPal Sandbox host. "
        "MerchantShield AI is Sandbox-only (rule R4). "
        f"Use {DEFAULT_PAYPAL_SANDBOX_BASE_URL}."
    )


class Settings(BaseSettings):
    """Environment-driven settings. Field names map to upper-case env vars."""

    # env_file defaults to None here so that constructing Settings() directly
    # -- which tests do -- never picks up a developer's real .env. The
    # application goes through get_settings(), which passes the resolved file.
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    demo_mode: bool = False
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None
    paypal_base_url: str = DEFAULT_PAYPAL_SANDBOX_BASE_URL
    paypal_mode: PayPalMode = "auto"
    llm_provider: LlmProvider = "none"
    llm_api_key: str | None = None
    llm_model: str | None = None
    database_url: str = "sqlite:///./merchantshield.db"
    app_base_url: str = "http://127.0.0.1:8000"
    port: int = Field(default=8000, ge=1, le=65535)

    @field_validator("paypal_base_url")
    @classmethod
    def _no_production_paypal(cls, value: str) -> str:
        return validate_paypal_base_url(value)

    # ------------------------------------------------------------------
    @property
    def demo_mode_was_explicit(self) -> bool:
        """True when DEMO_MODE was set deliberately, in the shell or in .env.

        A silent default must never be mistaken for an explicit choice, so the
        startup warning fires only when this is False.
        """
        if "DEMO_MODE" in os.environ or "demo_mode" in os.environ:
            return True
        return _dotenv_defines("DEMO_MODE", resolve_env_file())

    @property
    def has_paypal_credentials(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret)

    def safe_dump(self) -> dict[str, Any]:
        """Configuration snapshot that is safe to log or return over HTTP.

        Secrets are never included - not even masked-but-recoverable forms.
        """
        return {
            "demo_mode": self.demo_mode,
            "paypal_base_url": self.paypal_base_url,
            "paypal_mode": self.paypal_mode,
            "paypal_credentials_present": self.has_paypal_credentials,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "app_base_url": self.app_base_url,
            "port": self.port,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Call :func:`reset_settings_cache` in tests.

    This is the only place that loads ``.env``, so the file is found no matter
    which directory uvicorn was launched from (the README has you run it from
    ``backend/``, while ``.env`` lives at the project root).
    """
    env_file = resolve_env_file()
    if env_file is None:
        return Settings()
    return Settings(_env_file=env_file)


def reset_settings_cache() -> None:
    """Drop the cached Settings so a test can change the environment."""
    get_settings.cache_clear()
