"""Command line: ``news-summarizer "topic"`` (or ``python -m news_summarizer "topic"``)."""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import sys
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from typing import TextIO

from dotenv import load_dotenv

from .config import MAX_PAGE_SIZE, ConfigError, Settings
from .news import NewsError
from .pipeline import summarize_topic
from .summarizer import ArticleSummary, FatalSummaryError

EXIT_OK = 0
EXIT_SOME_FAILED = 1  # at least one article could not be summarized
EXIT_USAGE = 2  # missing or invalid configuration
EXIT_SERVICE = 3  # NewsAPI or OpenAI refused the whole run


def _limit(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a whole number") from None
    if not 1 <= number <= MAX_PAGE_SIZE:
        raise argparse.ArgumentTypeError(f"must be from 1 to {MAX_PAGE_SIZE}")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="news-summarizer",
        description="Fetch recent news about a topic from NewsAPI and summarize each article.",
    )
    parser.add_argument("topic", help='what to search for, for example "solid state batteries"')
    parser.add_argument(
        "-n", "--limit", type=_limit, help="number of articles (default: NEWS_PAGE_SIZE or 5)"
    )
    parser.add_argument(
        "--language", help="two letter language code, for example en (default: NEWS_LANGUAGE)"
    )
    parser.add_argument("--model", help="OpenAI model (default: OPENAI_MODEL)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("-v", "--verbose", action="store_true", help="log what happens to stderr")
    return parser


def _is_control(ch: str) -> bool:
    """Unicode category C*: C0 and C1 controls, bidi and other format characters (also the invisible
    "tag" characters), private use, unassigned. A byte check (< 0x20) misses most of them."""
    return unicodedata.category(ch).startswith("C")


def clean(text: str) -> str:
    """Article titles, model output and remote error messages are untrusted: drop everything
    that can drive a terminal or hide text (escape sequences, C1 controls, bidi overrides).
    Newlines stay."""
    return "".join(ch for ch in text if ch == "\n" or not _is_control(ch))


def _escape_controls(json_text: str) -> str:
    """JSON escapes characters below 0x20 itself but, with ensure_ascii=False, writes C1, bidi and
    tag characters raw. Turn those into \\uXXXX escapes: still the same JSON, safe to show in a
    terminal. The newlines of the indentation are structure and stay."""
    out: list[str] = []
    for ch in json_text:
        if ch != "\n" and _is_control(ch):
            code = ord(ch)
            if code > 0xFFFF:  # JSON spells these as a surrogate pair
                code -= 0x10000
                out.append(f"\\u{0xD800 + (code >> 10):04x}\\u{0xDC00 + (code & 0x3FF):04x}")
            else:
                out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    return "".join(out)


def render_text(results: Sequence[ArticleSummary]) -> str:
    lines: list[str] = []
    for index, item in enumerate(results, 1):
        article = item.article
        lines.append(f"{index}. {clean(article.title)}")
        lines.append(
            f"   {clean(article.source)}" + (f" - {clean(article.url)}" if article.url else "")
        )
        body = item.summary if item.ok else f"[no summary: {item.error}]"
        lines.extend("   " + line for line in clean(body or "").splitlines())
        lines.append("")
    return "\n".join(lines).rstrip("\n")


def render_json(results: Sequence[ArticleSummary]) -> str:
    return _escape_controls(
        json.dumps(
            [
                {
                    "title": item.article.title,
                    "source": item.article.source,
                    "url": item.article.url,
                    "summary": item.summary,
                    "error": item.error,
                }
                for item in results
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    run: Callable[..., list[ArticleSummary]] = summarize_topic,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=err,
    )

    if environ is None:
        load_dotenv()  # a local .env, if there is one; the process environment wins
        environ = os.environ
    try:
        settings = Settings.from_env(environ)
    except ConfigError as exc:
        print(f"error: {clean(str(exc))}. See .env.example.", file=err)
        return EXIT_USAGE

    overrides: dict[str, object] = {}
    if args.limit is not None:
        overrides["page_size"] = args.limit
    if args.language:
        overrides["news_language"] = args.language
    if args.model:
        overrides["openai_model"] = args.model
    settings = dataclasses.replace(settings, **overrides)

    try:
        results = run(args.topic, settings)
    except (NewsError, FatalSummaryError) as exc:
        print(f"error: {clean(str(exc))}", file=err)
        return EXIT_SERVICE

    if args.json:
        print(render_json(results), file=out)
    elif results:
        print(render_text(results), file=out)
    else:
        print(f"No articles found for {clean(args.topic)!r}.", file=out)
    return EXIT_SOME_FAILED if any(not item.ok for item in results) else EXIT_OK
