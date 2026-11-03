"""Shared fixtures: demo settings, a fake NewsAPI transport and a fake OpenAI client."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import httpx2
import openai
import pytest

from news_summarizer.config import Settings

NEWS_KEY = "news-key-demo-0001"
OPENAI_KEY = "sk-demo-key-0002"


@pytest.fixture(autouse=True)
def _no_dotenv_and_no_real_egress(monkeypatch):
    """Tests never read a developer's .env and never reach the real services."""
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    for name in ("NEWS_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def settings() -> Settings:
    return Settings(news_api_key=NEWS_KEY, openai_api_key=OPENAI_KEY, openai_model="demo-model")


def news_payload(*articles: dict) -> dict:
    return {"status": "ok", "totalResults": len(articles), "articles": list(articles)}


def make_article(n: int = 1, **overrides) -> dict:
    article = {
        "source": {"id": None, "name": f"Demo Daily {n}"},
        "author": f"Author {n}",
        "title": f"Headline number {n}",
        "description": f"Description of story {n}.",
        "url": f"https://news.example.test/story-{n}",
        "content": f"Body text of story {n} goes on for a while… [+{1000 + n} chars]",
    }
    article.update(overrides)
    return article


class NewsRecorder:
    """An httpx transport that records the requests and answers with a canned response."""

    def __init__(self, response: httpx.Response | Exception):
        self.response = response
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


@pytest.fixture
def news():
    def build(payload=None, status=200, error: Exception | None = None) -> NewsRecorder:
        if error is not None:
            return NewsRecorder(error)
        return NewsRecorder(httpx.Response(status, json=payload))

    return build


class FakeOpenAI:
    """Stands in for openai.OpenAI: answers with the given texts, or raises the given errors."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls: list[dict] = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        answer = self.answers[min(len(self.calls), len(self.answers)) - 1]
        if isinstance(answer, Exception):
            raise answer
        return SimpleNamespace(output_text=answer)


@pytest.fixture
def fake_openai():
    return FakeOpenAI


def status_error(cls, status: int) -> openai.APIStatusError:
    request = httpx2.Request("POST", "http://openai.example.test/v1/responses")
    return cls(
        "provider text that must not be shown",
        response=httpx2.Response(status, request=request),
        body=None,
    )


def connection_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(
        request=httpx2.Request("POST", "http://openai.example.test/v1/responses")
    )


def dump(value) -> str:
    return json.dumps(value, default=str)
