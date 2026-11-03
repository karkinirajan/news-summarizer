"""Topic in, summaries out: fetch the articles, summarize each one."""

from __future__ import annotations

import httpx

from .config import Settings
from .news import fetch_articles
from .summarizer import ArticleSummary, OpenAIClient, Summarizer, make_client, summarize_articles


def summarize_topic(
    topic: str,
    settings: Settings,
    *,
    news_client: httpx.Client | None = None,
    openai_client: OpenAIClient | None = None,
) -> list[ArticleSummary]:
    articles = fetch_articles(topic, settings, client=news_client)
    if not articles:
        return []
    summarizer = Summarizer(
        openai_client if openai_client is not None else make_client(settings),
        settings.openai_model,
        max_article_chars=settings.max_article_chars,
    )
    return summarize_articles(articles, summarizer)
