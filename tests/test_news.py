import httpx
import pytest

from news_summarizer.news import Article, NewsError, fetch_articles

from .conftest import NEWS_KEY, make_article, news_payload


def test_the_request_has_the_topic_the_page_size_and_the_key_in_a_header(settings, news):
    rec = news(news_payload(make_article(1)))
    fetch_articles("solid state & more", settings, client=rec.client())
    (request,) = rec.requests
    assert (
        request.url.params["q"] == "solid state & more"
    )  # encoded on the wire, intact once decoded
    assert request.url.params["pageSize"] == "5"
    assert request.headers["X-Api-Key"] == NEWS_KEY
    assert NEWS_KEY not in str(request.url)  # the old code put apiKey=... in the URL


def test_the_topic_is_url_encoded_not_interpolated(settings, news):
    rec = news(news_payload())
    fetch_articles("a&apiKey=evil#x", settings, client=rec.client())
    params = rec.requests[0].url.params
    assert params["q"] == "a&apiKey=evil#x" and "apiKey" not in params


def test_language_is_sent_only_when_set(settings, news):
    import dataclasses

    rec = news(news_payload())
    fetch_articles("x", settings, client=rec.client())
    assert "language" not in rec.requests[0].url.params
    rec = news(news_payload())
    fetch_articles("x", dataclasses.replace(settings, news_language="de"), client=rec.client())
    assert rec.requests[0].url.params["language"] == "de"


def test_articles_are_parsed(settings, news):
    rec = news(news_payload(make_article(1), make_article(2)))
    articles = fetch_articles("x", settings, client=rec.client())
    assert [a.title for a in articles] == ["Headline number 1", "Headline number 2"]
    first = articles[0]
    assert (first.source, first.url, first.author) == (
        "Demo Daily 1",
        "https://news.example.test/story-1",
        "Author 1",
    )


def test_removed_and_untitled_articles_are_dropped(settings, news):
    rec = news(
        news_payload(
            make_article(1, title="[Removed]"),
            make_article(2, title=None),
            make_article(3, title="   "),
            "not an object",
            make_article(4),
        )
    )
    assert [a.title for a in fetch_articles("x", settings, client=rec.client())] == [
        "Headline number 4"
    ]


def test_missing_fields_do_not_raise(settings, news):
    rec = news(news_payload({"title": "Only a title", "source": None}))
    (article,) = fetch_articles("x", settings, client=rec.client())
    assert article == Article("Only a title", "unknown source", "", None, None, None)
    assert article.text == ""


def test_no_articles_is_an_empty_list(settings, news):
    assert fetch_articles("x", settings, client=news(news_payload()).client()) == []


def test_an_empty_topic_is_refused_without_a_request(settings, news):
    rec = news(news_payload())
    with pytest.raises(NewsError, match="topic"):
        fetch_articles("   ", settings, client=rec.client())
    assert rec.requests == []


def test_http_errors_show_the_status_and_newsapis_message(settings, news):
    rec = news(
        {"status": "error", "code": "apiKeyInvalid", "message": "Your API key is invalid."},
        status=401,
    )
    with pytest.raises(NewsError) as caught:
        fetch_articles("x", settings, client=rec.client())
    assert "401" in str(caught.value) and "Your API key is invalid." in str(caught.value)


def test_the_key_is_scrubbed_if_the_message_echoes_it(settings, news):
    rec = news({"message": f"bad key {NEWS_KEY}"}, status=401)
    with pytest.raises(NewsError) as caught:
        fetch_articles("x", settings, client=rec.client())
    assert NEWS_KEY not in str(caught.value) and "***" in str(caught.value)


def test_an_error_page_that_is_not_json_still_gives_a_clean_error(settings):
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(502, text="<html>bad gateway</html>")
        )
    )
    with pytest.raises(NewsError, match="502"):
        fetch_articles("x", settings, client=client)


def test_network_failures_name_the_kind_but_not_the_url(settings, news):
    rec = news(error=httpx.ConnectError("failed to connect to https://newsapi.test/?apiKey=SECRET"))
    with pytest.raises(NewsError) as caught:
        fetch_articles("x", settings, client=rec.client())
    assert "ConnectError" in str(caught.value)
    assert "SECRET" not in str(caught.value) and "newsapi.test" not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


@pytest.mark.parametrize("body", [b"not json", b'{"articles": "nope"}', b"[]", b'{"status": "ok"}'])
def test_unexpected_bodies_are_reported(settings, body):
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body))
    )
    with pytest.raises(NewsError):
        fetch_articles("x", settings, client=client)


def test_article_text_joins_description_and_content_and_drops_the_truncation_marker():
    article = Article("t", "s", "u", None, "A description.", "More body text … [+4321 chars]")
    assert article.text == "A description.\n\nMore body text"


@pytest.mark.parametrize(
    ("description", "content", "expected"),
    [
        ("Same text.", "Same text.", "Same text."),
        ("Same text", "Same text and a bit more [+12 chars]", "Same text and a bit more"),
        (None, "Only content [+5 chars]", "Only content"),
        ("Only description", None, "Only description"),
        (None, None, ""),
        ("  ", "[+9 chars]", ""),
    ],
)
def test_article_text_cases(description, content, expected):
    assert Article("t", "s", "u", None, description, content).text == expected
