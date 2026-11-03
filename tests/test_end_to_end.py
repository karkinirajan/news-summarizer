"""The whole program against local servers: real httpx, the real OpenAI SDK, no mocks in between."""

import io
import json
import socket

import pytest

from news_summarizer.cli import main

from . import fakes
from .conftest import NEWS_KEY, OPENAI_KEY, make_article


@pytest.fixture
def servers(monkeypatch):
    started = []

    def start(articles, news_key=NEWS_KEY, openai_key=OPENAI_KEY):
        news = fakes.start_news_server(articles, news_key)
        openai_server = fakes.start_openai_server(openai_key)
        started.extend([news, openai_server])
        monkeypatch.setenv("OPENAI_BASE_URL", openai_server.base + "/v1")
        return news, openai_server

    # Anything that tries a real service goes to a dead proxy and fails.
    # The local servers are exempt.
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
    ):
        monkeypatch.setenv(name, "http://127.0.0.1:9")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    yield start
    for server in started:
        server.stop()


def environ(news, **extra):
    return {
        "NEWS_API_KEY": NEWS_KEY,
        "OPENAI_API_KEY": OPENAI_KEY,
        "OPENAI_MODEL": "demo-model",
        "NEWS_API_URL": news.base + "/v2/everything",
        **extra,
    }


def run(args, env):
    out, err = io.StringIO(), io.StringIO()
    code = main(args, environ=env, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def test_a_full_run(servers):
    news, openai_server = servers(
        [make_article(1), make_article(2, title="[Removed]"), make_article(3), make_article(4)]
    )
    code, out, err = run(["solid state batteries", "-n", "3", "--json"], environ(news))

    assert code == 0 and err == ""
    results = json.loads(out)
    assert [r["title"] for r in results] == [
        "Headline number 1",
        "Headline number 3",
        "Headline number 4",
    ]
    assert results[0]["summary"] == "Summary of: Headline number 1"

    (news_request,) = news.requests
    assert news_request["query"]["q"] == ["solid state batteries"]
    assert news_request["query"]["pageSize"] == ["3"]
    assert news_request["headers"]["x-api-key"] == NEWS_KEY
    assert "apiKey" not in news_request["query"]

    assert len(openai_server.requests) == 3
    first = openai_server.requests[0]
    assert first["path"] == "/v1/responses"
    assert first["headers"]["authorization"] == f"Bearer {OPENAI_KEY}"
    assert first["body"]["model"] == "demo-model"
    assert "Description of story 1." in first["body"]["input"]
    assert "[+1001 chars]" not in first["body"]["input"]  # NewsAPI's truncation marker is removed


def test_text_output_never_contains_a_key(servers):
    news, _ = servers([make_article(1)])
    code, out, err = run(["x"], environ(news))
    assert code == 0 and "1. Headline number 1" in out
    for key in (NEWS_KEY, OPENAI_KEY):
        assert key not in out and key not in err


def test_one_refused_article_gives_exit_code_one_and_the_rest_are_kept(servers):
    news, _ = servers([make_article(1), make_article(2, title="BREAK this one"), make_article(3)])
    code, out, _ = run(["x"], environ(news))
    assert code == 1
    assert "Summary of: Headline number 1" in out and "Summary of: Headline number 3" in out
    assert "[no summary: OpenAI answered HTTP 400]" in out


def test_a_rejected_openai_key_stops_the_run_after_one_request(servers):
    news, openai_server = servers([make_article(1), make_article(2), make_article(3)])
    code, out, err = run(["x"], environ(news, OPENAI_API_KEY="sk-wrong-key"))
    assert code == 3 and out == ""
    assert "refused" in err and "sk-wrong-key" not in err
    assert len(openai_server.requests) == 1


def test_a_rejected_news_key_exits_3_and_never_calls_openai(servers):
    news, openai_server = servers([make_article(1)])
    code, out, err = run(["x"], environ(news, NEWS_API_KEY="news-wrong-key"))
    assert code == 3 and out == ""
    assert "401" in err and "Your API key is invalid." in err and "news-wrong-key" not in err
    assert openai_server.requests == []


def test_an_unreachable_news_server_is_a_clean_error(servers):
    news, _ = servers([])
    with socket.socket() as sock:  # a port nobody listens on
        sock.bind(("127.0.0.1", 0))
        dead = sock.getsockname()[1]
    env = environ(news, NEWS_API_URL=f"http://127.0.0.1:{dead}/v2/everything", REQUEST_TIMEOUT="2")
    code, out, err = run(["x"], env)
    assert code == 3 and out == "" and "could not reach NewsAPI" in err
    assert "Traceback" not in err


def test_no_articles_makes_no_openai_request(servers):
    news, openai_server = servers([])
    code, out, _ = run(["nothing here"], environ(news))
    assert code == 0 and "No articles found" in out
    assert openai_server.requests == []


def test_the_default_urls_are_never_used_in_these_tests(servers, monkeypatch):
    """Without NEWS_API_URL it would go to newsapi.org; the dead proxy turns that into an error."""
    news, _ = servers([make_article(1)])
    env = environ(news)
    del env["NEWS_API_URL"]
    env["REQUEST_TIMEOUT"] = "3"
    code, _, err = run(["x"], env)
    assert code == 3 and "could not reach NewsAPI" in err
