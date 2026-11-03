"""Fetching articles from NewsAPI (https://newsapi.org/docs/endpoints/everything)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from .config import Settings

# NewsAPI cuts `content` at about 200 characters and ends it with "[+1234 chars]"
_TRUNCATION_MARKER = re.compile(r"\s*(?:…|\.\.\.)?\s*\[\+\d+ chars\]\s*$")
# What NewsAPI sends for an article its source asked to take down
_REMOVED_TITLE = "[Removed]"


class NewsError(Exception):
    """NewsAPI could not be reached or refused the request. Never contains the API key."""


@dataclass(frozen=True, slots=True)
class Article:
    title: str
    source: str
    url: str
    author: str | None
    description: str | None
    content: str | None

    @property
    def text(self) -> str:
        """What there is to summarize: description and (truncated) content, without repeats."""
        parts: list[str] = []
        for piece in (self.description, _TRUNCATION_MARKER.sub("", self.content or "")):
            piece = (piece or "").strip()
            if not piece or any(piece in existing for existing in parts):
                continue
            # the content often starts with the description: keep only the longer of the two
            parts = [existing for existing in parts if existing not in piece]
            parts.append(piece)
        return "\n\n".join(parts)


def _parse_article(raw: object) -> Article | None:
    if not isinstance(raw, dict):
        return None
    title = (raw.get("title") or "").strip()
    if not title or title == _REMOVED_TITLE:
        return None
    source = raw.get("source")
    source_name = source.get("name") if isinstance(source, dict) else None
    return Article(
        title=title,
        source=(source_name or "unknown source").strip(),
        url=(raw.get("url") or "").strip(),
        author=raw.get("author") or None,
        description=raw.get("description") or None,
        content=raw.get("content") or None,
    )


def _error_message(response: httpx.Response, api_key: str) -> str:
    message = ""
    try:
        body = response.json()
        if isinstance(body, dict):
            message = str(body.get("message") or "")
    except ValueError:
        pass
    # NewsAPI's own messages do not contain the key, but make sure of it
    message = message.replace(api_key, "***") if api_key else message
    return f"NewsAPI answered HTTP {response.status_code}" + (f": {message}" if message else "")


def fetch_articles(
    topic: str, settings: Settings, *, client: httpx.Client | None = None
) -> list[Article]:
    """Up to `settings.page_size` articles about `topic`. Articles without a title are dropped."""
    topic = topic.strip()
    if not topic:
        raise NewsError("the topic is empty")

    params: dict[str, str | int] = {"q": topic, "pageSize": settings.page_size}
    if settings.news_language:
        params["language"] = settings.news_language
    # The key travels in a header. In the query string it ends up in logs and in exception messages.
    headers = {"X-Api-Key": settings.news_api_key}

    http = client if client is not None else httpx.Client(timeout=settings.request_timeout)
    try:
        response = http.get(settings.news_api_url, params=params, headers=headers)
    except httpx.HTTPError as exc:
        # The exception text can contain the request URL: only say what kind of failure it was
        raise NewsError(f"could not reach NewsAPI ({type(exc).__name__})") from None
    finally:
        if client is None:
            http.close()

    if response.status_code != 200:
        raise NewsError(_error_message(response, settings.news_api_key))
    try:
        body = response.json()
    except ValueError:
        raise NewsError("NewsAPI sent a response that is not JSON") from None
    raw_articles = body.get("articles") if isinstance(body, dict) else None
    if not isinstance(raw_articles, list):
        raise NewsError("NewsAPI sent a response without an article list")

    articles = (_parse_article(raw) for raw in raw_articles)
    return [article for article in articles if article is not None]
