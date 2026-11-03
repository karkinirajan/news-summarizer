"""`.env.example` tells a new user what to set: it must list every variable the code reads."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def variables_read() -> set[str]:
    source = (ROOT / "src" / "news_summarizer" / "config.py").read_text()
    direct = re.findall(r"""environ(?:\.get)?\(?\[?\s*["']([A-Z][A-Z0-9_]+)["']""", source)
    helpers = re.findall(r"""_(?:int|float)\(\s*environ,\s*["']([A-Z][A-Z0-9_]+)["']""", source)
    keys = re.findall(r"""for name in \(([^)]*)\)""", source, re.S)
    listed = [n for group in keys for n in re.findall(r"""["']([A-Z][A-Z0-9_]+)["']""", group)]
    return set(direct) | set(helpers) | set(listed)


def variables_documented() -> set[str]:
    text = (ROOT / ".env.example").read_text()
    return set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", text, re.M))


def test_the_scan_finds_the_variables():
    assert {
        "NEWS_API_KEY",
        "OPENAI_API_KEY",
        "NEWS_PAGE_SIZE",
        "REQUEST_TIMEOUT",
    } <= variables_read()
    assert len(variables_read()) >= 8


def test_every_variable_the_code_reads_is_in_env_example():
    assert sorted(variables_read() - variables_documented()) == []


def test_env_example_has_only_demo_values():
    text = (ROOT / ".env.example").read_text()
    assert not re.search(r"sk-[A-Za-z0-9]{20,}", text)
