# News-Summarizer

Fetches recent news about a topic from [NewsAPI](https://newsapi.org/) and has an OpenAI model summarize
each article in two or three sentences.

```console
$ news-summarizer "solid state batteries" -n 3
1. Headline of the first article
   Some Daily - https://example.com/story-1
   Two or three sentences with the main facts.

2. ...
```

## Contents

1. [Features](#features)
2. [Quickstart](#quickstart)
3. [Configuration](#configuration)
4. [Using it from Python](#using-it-from-python)
5. [Project structure](#project-structure)
6. [Testing](#testing)
7. [Limits](#limits)
8. [Versions](#versions)
9. [License](#license)

## Features

* One command, text or `--json` output, a clear exit code (below).
* One summary request per article. A failure on one article is shown next to it and the others still run.
* A refused API key stops the run after the first request instead of repeating the same failure.
* The NewsAPI key goes in a request header, never in the URL, and no error message or log line contains a key.
* Article titles and model output are untrusted text: control characters (terminal escape sequences) are removed
  before they are printed.

Exit codes: `0` all summarized, `1` some articles could not be summarized, `2` missing or invalid configuration
or usage, `3` NewsAPI or OpenAI refused the whole run.

## Quickstart

You need [uv](https://docs.astral.sh/uv/), a [NewsAPI](https://newsapi.org/account) key and an
[OpenAI](https://platform.openai.com/api-keys) key.

```bash
uv sync
cp .env.example .env          # then put your two keys in it
uv run news-summarizer "solid state batteries" -n 3
uv run news-summarizer "solid state batteries" --json
uv run news-summarizer --help
```

`python -m news_summarizer "topic"` works too. The command reads `.env` from the current directory; real
environment variables win over it.

## Configuration

All settings are environment variables; `.env.example` lists them (a test keeps that file complete).

| Variable | Default | |
|---|---|---|
| `NEWS_API_KEY` | required | NewsAPI key |
| `OPENAI_API_KEY` | required | OpenAI key |
| `OPENAI_MODEL` | `gpt-5.5` | the summarizing model. The default is the model named in the OpenAI SDK's README; check that your account can use it, or set another |
| `NEWS_PAGE_SIZE` | `5` | articles per run, 1 to 100 (`-n` overrides) |
| `NEWS_LANGUAGE` | any | two letter code, for example `en` (`--language` overrides) |
| `REQUEST_TIMEOUT` | `30` | seconds for each HTTP request |
| `MAX_ARTICLE_CHARS` | `4000` | characters of an article sent to the model |
| `NEWS_API_URL` | NewsAPI's | endpoint, to point at a test server |

The OpenAI SDK also reads `OPENAI_BASE_URL`.

## Using it from Python

```python
from news_summarizer import Settings, summarize_topic

settings = Settings.from_env()
for item in summarize_topic("solid state batteries", settings):
    print(item.article.title, "->", item.summary or item.error)
```

## Project structure

```
src/news_summarizer/
  config.py       Settings from the environment (keys are kept out of repr)
  news.py         NewsAPI client: Article, fetch_articles, NewsError
  summarizer.py   OpenAI Responses API: Summarizer, summarize_articles, error handling
  pipeline.py     summarize_topic: fetch, then summarize each article
  cli.py          the news-summarizer command
tests/            unit tests, plus end-to-end tests against local fake NewsAPI and OpenAI servers
.github/workflows/ci.yml   lint, format check, tests
```

## Testing

```bash
uv run pytest -q --cov
uv run ruff check . && uv run ruff format --check .
```

88 tests, 99 % line and branch coverage (the rest is the `python -m` module, which only runs in a subprocess).
The end-to-end tests run the real `httpx` and OpenAI SDK clients against local servers, with real services
blocked behind a dead proxy. **No live NewsAPI or OpenAI call has been made with this code**: no keys were
used, only demo values.

## Limits

* NewsAPI cuts an article's `content` at about 200 characters. The summary is built from the description and
  that snippet, not from the full article, so it is only as good as what NewsAPI sends.
* Each article is one OpenAI request, so a run with `-n 100` makes 100 requests.
* The model is told to use only the supplied text, but a summary is still a model's output: check it before
  relying on it.

## Versions

Python 3.13, OpenAI SDK 3.x, httpx 0.28. Details in [VERSIONS.md](VERSIONS.md); what changed from the original
script in [work-done.md](work-done.md).

## License

MIT, see [LICENSE](LICENSE).
