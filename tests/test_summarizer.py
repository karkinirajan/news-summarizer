import openai
import pytest

from news_summarizer.news import Article
from news_summarizer.summarizer import (
    INSTRUCTIONS,
    FatalSummaryError,
    Summarizer,
    SummaryError,
    build_input,
    describe_error,
    summarize_articles,
)

from .conftest import FakeOpenAI, connection_error, status_error


def article(n=1, **kw):
    fields = dict(
        title=f"Headline {n}",
        source="Demo Daily",
        url=f"https://x.test/{n}",
        author=None,
        description=f"Description {n}.",
        content=None,
    )
    fields.update(kw)
    return Article(**fields)


def test_the_request_has_the_model_the_instructions_and_the_article():
    client = FakeOpenAI("A short summary.")
    text = Summarizer(client, "demo-model").summarize(article(1))
    assert text == "A short summary."
    (call,) = client.calls
    assert call["model"] == "demo-model"
    assert call["instructions"] == INSTRUCTIONS
    assert "Title: Headline 1" in call["input"] and "Description 1." in call["input"]
    assert "<article>" in call["input"] and "</article>" in call["input"]


def test_the_summary_is_stripped():
    assert Summarizer(FakeOpenAI("  \n  Summary.\n "), "m").summarize(article()) == "Summary."


def test_long_text_is_cut_to_the_limit_and_the_cut_is_marked():
    long = "word " * 5000
    prompt = build_input(article(description=long), max_chars=300)
    body = prompt.split("<article>\n")[1].split("\n</article>")[0]
    assert len(body) <= 300 + len(" [cut]") and body.endswith("[cut]")


def test_short_text_is_not_marked_as_cut():
    assert "[cut]" not in build_input(article(), max_chars=4000)


def test_an_article_without_text_is_not_sent_to_the_model():
    client = FakeOpenAI("never used")
    with pytest.raises(SummaryError, match="no text"):
        Summarizer(client, "m").summarize(article(description=None, content=None))
    assert client.calls == []


@pytest.mark.parametrize("answer", ["", "   ", None])
def test_an_empty_answer_is_an_error(answer):
    with pytest.raises(SummaryError, match="empty"):
        Summarizer(FakeOpenAI(answer), "m").summarize(article())


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (status_error(openai.RateLimitError, 429), "HTTP 429"),
        (status_error(openai.BadRequestError, 400), "HTTP 400"),
        (status_error(openai.InternalServerError, 500), "HTTP 500"),
        (connection_error(), "could not reach OpenAI"),
    ],
)
def test_api_failures_become_short_errors_without_the_provider_text(error, expected):
    with pytest.raises(SummaryError) as caught:
        Summarizer(FakeOpenAI(error), "m").summarize(article())
    assert expected in str(caught.value)
    assert "provider text" not in str(caught.value)
    assert not isinstance(caught.value, FatalSummaryError)


@pytest.mark.parametrize(
    "error",
    [
        status_error(openai.AuthenticationError, 401),
        status_error(openai.PermissionDeniedError, 403),
    ],
)
def test_a_refused_key_is_fatal(error):
    with pytest.raises(FatalSummaryError, match="refused"):
        Summarizer(FakeOpenAI(error), "m").summarize(article())


def test_describe_error_has_a_fallback():
    assert "OpenAIError" in describe_error(openai.OpenAIError("x"))


def test_one_failed_article_does_not_stop_the_others():
    client = FakeOpenAI("First.", status_error(openai.BadRequestError, 400), "Third.")
    results = summarize_articles([article(1), article(2), article(3)], Summarizer(client, "m"))
    assert [r.ok for r in results] == [True, False, True]
    assert [r.summary for r in results] == ["First.", None, "Third."]
    assert "HTTP 400" in results[1].error and results[1].article.title == "Headline 2"


def test_an_article_without_text_is_reported_and_skipped():
    client = FakeOpenAI("Only one call.")
    results = summarize_articles(
        [article(1, description=None), article(2)], Summarizer(client, "m")
    )
    assert [r.ok for r in results] == [False, True]
    assert len(client.calls) == 1


def test_a_refused_key_stops_after_the_first_request():
    client = FakeOpenAI(status_error(openai.AuthenticationError, 401))
    with pytest.raises(FatalSummaryError):
        summarize_articles([article(1), article(2), article(3)], Summarizer(client, "m"))
    assert len(client.calls) == 1  # not three identical failing calls


def test_no_articles_no_results():
    assert summarize_articles([], Summarizer(FakeOpenAI("x"), "m")) == []
