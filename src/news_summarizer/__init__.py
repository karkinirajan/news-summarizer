"""Fetch news about a topic and summarize each article."""

from .config import ConfigError, Settings
from .news import Article, NewsError, fetch_articles
from .pipeline import summarize_topic
from .summarizer import ArticleSummary, FatalSummaryError, Summarizer, SummaryError

__all__ = [
    "Article",
    "ArticleSummary",
    "ConfigError",
    "FatalSummaryError",
    "NewsError",
    "Settings",
    "Summarizer",
    "SummaryError",
    "fetch_articles",
    "summarize_topic",
]
