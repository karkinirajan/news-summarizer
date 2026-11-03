import pytest

from news_summarizer.config import DEFAULT_MODEL, DEFAULT_NEWS_URL, ConfigError, Settings

KEYS = {"NEWS_API_KEY": "news-demo", "OPENAI_API_KEY": "sk-demo"}


def test_defaults():
    s = Settings.from_env(KEYS)
    assert (s.openai_model, s.news_api_url, s.news_language) == (
        DEFAULT_MODEL,
        DEFAULT_NEWS_URL,
        None,
    )
    assert (s.page_size, s.request_timeout, s.max_article_chars) == (5, 30.0, 4000)


def test_values_are_read_and_stripped():
    s = Settings.from_env(
        {
            "NEWS_API_KEY": "  news-demo  ",
            "OPENAI_API_KEY": "sk-demo\n",
            "OPENAI_MODEL": " some-model ",
            "NEWS_API_URL": "http://localhost:9/v2/everything",
            "NEWS_LANGUAGE": "de",
            "NEWS_PAGE_SIZE": "12",
            "REQUEST_TIMEOUT": "2.5",
            "MAX_ARTICLE_CHARS": "800",
        }
    )
    assert s.news_api_key == "news-demo" and s.openai_api_key == "sk-demo"
    assert (s.openai_model, s.news_language, s.page_size) == ("some-model", "de", 12)
    assert (s.news_api_url, s.request_timeout, s.max_article_chars) == (
        "http://localhost:9/v2/everything",
        2.5,
        800,
    )


@pytest.mark.parametrize("missing", ["NEWS_API_KEY", "OPENAI_API_KEY"])
def test_a_missing_key_is_named(missing):
    environ = {k: v for k, v in KEYS.items() if k != missing}
    with pytest.raises(ConfigError, match=missing):
        Settings.from_env(environ)


def test_blank_keys_count_as_missing_and_all_missing_names_are_listed():
    with pytest.raises(ConfigError) as caught:
        Settings.from_env({"NEWS_API_KEY": "   ", "OPENAI_API_KEY": ""})
    assert "NEWS_API_KEY" in str(caught.value) and "OPENAI_API_KEY" in str(caught.value)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("NEWS_PAGE_SIZE", "0"),
        ("NEWS_PAGE_SIZE", "101"),
        ("NEWS_PAGE_SIZE", "five"),
        ("REQUEST_TIMEOUT", "0"),
        ("REQUEST_TIMEOUT", "-3"),
        ("REQUEST_TIMEOUT", "soon"),
        ("MAX_ARTICLE_CHARS", "10"),
    ],
)
def test_invalid_numbers_are_refused_by_name(name, value):
    with pytest.raises(ConfigError, match=name):
        Settings.from_env({**KEYS, name: value})


def test_the_page_size_limits_are_accepted():
    assert Settings.from_env({**KEYS, "NEWS_PAGE_SIZE": "1"}).page_size == 1
    assert Settings.from_env({**KEYS, "NEWS_PAGE_SIZE": "100"}).page_size == 100


def test_keys_do_not_appear_in_repr_or_str(settings):
    for text in (repr(settings), str(settings)):
        assert "news-key-demo" not in text and "sk-demo-key" not in text


def test_the_process_environment_is_used_by_default(monkeypatch):
    monkeypatch.setenv("NEWS_API_KEY", "from-process")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-process")
    assert Settings.from_env().news_api_key == "from-process"
