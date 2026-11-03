import io
import json
import unicodedata

import pytest

from news_summarizer.cli import clean, main, render_json, render_text
from news_summarizer.news import Article, NewsError
from news_summarizer.summarizer import ArticleSummary, FatalSummaryError

ENV = {"NEWS_API_KEY": "news-demo", "OPENAI_API_KEY": "sk-demo"}


def art(n=1, **kw):
    fields = dict(
        title=f"Headline {n}",
        source="Demo Daily",
        url=f"https://x.test/{n}",
        author=None,
        description="d",
        content=None,
    )
    fields.update(kw)
    return Article(**fields)


def run_cli(args, results=None, error=None, environ=ENV):
    seen = {}

    def fake_run(topic, settings):
        seen.update(topic=topic, settings=settings)
        if error:
            raise error
        return results if results is not None else []

    out, err = io.StringIO(), io.StringIO()
    code = main(args, environ=environ, run=fake_run, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue(), seen


def test_text_output_and_exit_code_zero():
    code, out, err, seen = run_cli(
        ["solid state batteries"],
        [ArticleSummary(art(1), "One. Two."), ArticleSummary(art(2), "Three.")],
    )
    assert code == 0 and err == ""
    assert seen["topic"] == "solid state batteries"
    assert out.splitlines()[:4] == [
        "1. Headline 1",
        "   Demo Daily - https://x.test/1",
        "   One. Two.",
        "",
    ]
    assert "2. Headline 2" in out


def test_json_output():
    code, out, _, _ = run_cli(
        ["x", "--json"], [ArticleSummary(art(1), "S."), ArticleSummary(art(2), error="HTTP 400")]
    )
    data = json.loads(out)
    assert data[0] == {
        "title": "Headline 1",
        "source": "Demo Daily",
        "url": "https://x.test/1",
        "summary": "S.",
        "error": None,
    }
    assert data[1]["summary"] is None and data[1]["error"] == "HTTP 400"
    assert code == 1  # one article could not be summarized


def test_no_articles_says_so_and_is_not_an_error():
    code, out, _, _ = run_cli(["quiet topic"], [])
    assert code == 0 and "No articles found for 'quiet topic'" in out


def test_a_failed_article_is_shown_with_its_reason_and_exit_code_is_one():
    code, out, _, _ = run_cli(["x"], [ArticleSummary(art(1), error="OpenAI answered HTTP 400")])
    assert code == 1 and "[no summary: OpenAI answered HTTP 400]" in out


def test_missing_configuration_exits_2_naming_the_variables():
    code, out, err, seen = run_cli(["x"], environ={})
    assert code == 2 and out == "" and seen == {}
    assert "NEWS_API_KEY" in err and "OPENAI_API_KEY" in err and ".env.example" in err


@pytest.mark.parametrize(
    "error",
    [NewsError("NewsAPI answered HTTP 401"), FatalSummaryError("OpenAI refused the API key")],
)
def test_a_refused_run_exits_3_with_the_message_on_stderr(error):
    code, out, err, _ = run_cli(["x"], error=error)
    assert code == 3 and out == "" and str(error) in err


def test_options_override_the_settings():
    _, _, _, seen = run_cli(["x", "-n", "7", "--language", "fr", "--model", "other-model"], [])
    s = seen["settings"]
    assert (s.page_size, s.news_language, s.openai_model) == (7, "fr", "other-model")


def test_without_options_the_environment_settings_are_kept():
    _, _, _, seen = run_cli(["x"], [], environ={**ENV, "NEWS_PAGE_SIZE": "9", "OPENAI_MODEL": "m1"})
    assert (seen["settings"].page_size, seen["settings"].openai_model) == (9, "m1")


@pytest.mark.parametrize("limit", ["0", "101", "many"])
def test_a_bad_limit_is_a_usage_error(limit, capsys):
    with pytest.raises(SystemExit) as caught:
        run_cli(["x", "-n", limit])
    assert caught.value.code == 2
    assert "limit" in capsys.readouterr().err


def test_the_topic_is_required(capsys):
    with pytest.raises(SystemExit):
        run_cli([])


def test_control_characters_are_removed_from_text_output():
    evil = ArticleSummary(
        art(1, title="Click\x1b[31m here\x07", source="Src\x1b]0;pwned\x07"),
        "Fine.\x1b[2J\x00Done.",
    )
    out = render_text([evil])
    assert "\x1b" not in out and "\x07" not in out and "\x00" not in out
    assert "Click[31m here" in out and "Fine.[2JDone." in out


def test_clean_keeps_newlines_and_unicode():
    assert clean("line one\nline two é ü 中") == "line one\nline two é ü 中"
    assert clean("a\tb\x7fc") == "abc"


def test_json_output_keeps_the_raw_text():
    # JSON escapes control characters itself, so nothing is stripped there
    data = json.loads(render_json([ArticleSummary(art(1, title="a\x1bb"), "s")]))
    assert data[0]["title"] == "a\x1bb"


def test_the_topic_in_the_no_articles_message_is_cleaned():
    _, out, _, _ = run_cli(["bad\x1b[31mtopic"], [])
    assert "\x1b" not in out


def test_the_process_environment_is_used_when_no_environ_is_given(monkeypatch):
    monkeypatch.setenv("NEWS_API_KEY", "news-from-process")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-process")
    seen = {}

    def fake_run(topic, settings):
        seen["settings"] = settings
        return []

    out = io.StringIO()
    assert main(["x"], run=fake_run, stdout=out, stderr=io.StringIO()) == 0
    assert seen["settings"].news_api_key == "news-from-process"


def test_without_any_configuration_the_real_program_exits_2(tmp_path):
    """A real process through `python -m`: no keys, no .env (dotenv switched off), exit code 2."""
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k not in ("NEWS_API_KEY", "OPENAI_API_KEY")}
    env["PYTHON_DOTENV_DISABLED"] = "1"
    done = subprocess.run(
        [sys.executable, "-m", "news_summarizer", "anything"],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 2
    assert "NEWS_API_KEY" in done.stderr and "OPENAI_API_KEY" in done.stderr
    assert "Traceback" not in done.stderr


def test_help_lists_the_options():
    import subprocess
    import sys

    done = subprocess.run(
        [sys.executable, "-m", "news_summarizer", "--help"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 0
    for option in ("--limit", "--language", "--model", "--json"):
        assert option in done.stdout


# What a hostile headline can carry: a C1 control (CSI, 0x9b), a bidi override, an invisible "tag"
# character, a zero width space and a plain escape sequence. None of them may reach a terminal.
HOSTILE = "ok\x9b31m‮evil\U000e0041​fine\x1b[2J"


def test_clean_removes_c1_bidi_tag_and_zero_width_characters():
    assert clean(HOSTILE) == "ok31mevilfine[2J"


def test_clean_keeps_ordinary_text_in_any_script():
    assert clean("Café 中文 العربية 😀\nsecond line") == "Café 中文 العربية 😀\nsecond line"


def test_text_output_is_free_of_control_characters():
    out = render_text([ArticleSummary(art(1, title=HOSTILE, source=HOSTILE), HOSTILE)])
    assert not any(unicodedata.category(c).startswith("C") and c != "\n" for c in out)


def test_json_output_has_no_raw_control_characters_and_still_round_trips():
    out = render_json([ArticleSummary(art(1, title=HOSTILE), HOSTILE)])
    assert not any(unicodedata.category(c).startswith("C") and c != "\n" for c in out)
    data = json.loads(out)
    assert data[0]["title"] == HOSTILE and data[0]["summary"] == HOSTILE


def test_json_output_keeps_readable_non_ascii_text():
    out = render_json([ArticleSummary(art(1, title="Café 中文 😀"), "s")])
    assert "Café 中文 😀" in out


@pytest.mark.parametrize(
    "error", [NewsError(f"NewsAPI answered HTTP 401: {HOSTILE}"), FatalSummaryError(HOSTILE)]
)
def test_error_text_from_a_remote_service_is_cleaned_before_it_reaches_stderr(error):
    _, _, err, _ = run_cli(["x"], error=error)
    assert not any(unicodedata.category(c).startswith("C") and c != "\n" for c in err)
    assert "ok31mevilfine" in err
