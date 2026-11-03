"""Settings, read from the environment (a local .env file is loaded by the CLI, see cli.py)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

# The model named in the OpenAI SDK's README at the time of writing.
# Set OPENAI_MODEL to use another one.
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_NEWS_URL = "https://newsapi.org/v2/everything"

MAX_PAGE_SIZE = 100  # NewsAPI refuses larger pages


class ConfigError(Exception):
    """A setting is missing or invalid. The message names the variable, never its value."""


def _int(environ: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    raw = environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number from {low} to {high}") from None
    if not low <= value <= high:
        raise ConfigError(f"{name} must be a whole number from {low} to {high}")
    return value


def _float(environ: Mapping[str, str], name: str, default: float) -> float:
    raw = environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a positive number of seconds") from None
    if value <= 0:
        raise ConfigError(f"{name} must be a positive number of seconds")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    # repr=False: a Settings object ends up in logs and tracebacks, the keys must not
    news_api_key: str = field(repr=False)
    openai_api_key: str = field(repr=False)
    openai_model: str = DEFAULT_MODEL
    news_api_url: str = DEFAULT_NEWS_URL
    news_language: str | None = None
    page_size: int = 5
    request_timeout: float = 30.0
    max_article_chars: int = 4000

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        environ = os.environ if environ is None else environ
        missing = [
            name for name in ("NEWS_API_KEY", "OPENAI_API_KEY") if not environ.get(name, "").strip()
        ]
        if missing:
            raise ConfigError("Missing environment variables: " + ", ".join(missing))
        return cls(
            news_api_key=environ["NEWS_API_KEY"].strip(),
            openai_api_key=environ["OPENAI_API_KEY"].strip(),
            openai_model=environ.get("OPENAI_MODEL", "").strip() or DEFAULT_MODEL,
            news_api_url=environ.get("NEWS_API_URL", "").strip() or DEFAULT_NEWS_URL,
            news_language=environ.get("NEWS_LANGUAGE", "").strip() or None,
            page_size=_int(environ, "NEWS_PAGE_SIZE", 5, 1, MAX_PAGE_SIZE),
            request_timeout=_float(environ, "REQUEST_TIMEOUT", 30.0),
            max_article_chars=_int(environ, "MAX_ARTICLE_CHARS", 4000, 200, 100_000),
        )
