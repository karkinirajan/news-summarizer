# Versions

Exact versions of all 28 locked packages are in `uv.lock`; these are the ones that matter.

| Component | Version | Pinned in | Notes |
|---|---|---|---|
| Python | 3.13 (3.13.18 used for the tests) | `.python-version`, `requires-python = ">=3.13"` | |
| openai (Python SDK) | 3.42.1 (`>=3.35`) | `pyproject.toml`, `uv.lock` | v3 ships its own HTTP client (`httpx2`) |
| httpx | 0.28.1 (`>=0.28`) | `pyproject.toml`, `uv.lock` | used for NewsAPI |
| python-dotenv | 1.2.4 (`>=1.1`) | `pyproject.toml`, `uv.lock` | loads `.env` in the CLI only |
| pytest / pytest-cov | 9.2.0 / 7.1.0 | dev group | |
| ruff | 0.17.3 | dev group | rules `E F I B UP SIM S BLE RUF` |
| uv | 0.13.6 | used to build the lock | |
| hatchling | build backend | `pyproject.toml` | |

## The model

`OPENAI_MODEL` defaults to `gpt-5.5`. That is the model the OpenAI Python SDK's README (v3.35.1) uses in its
examples. It was **not** checked against any account, so treat it as a starting point and set the model you use.
The original script used `gpt-3.5-turbo-16k`, which is an old model name.

## What was removed

* The **Assistants API** (assistants, threads, runs, polling). OpenAI deprecated it in favour of the Responses
  API and announced its shutdown for August 26, 2026. That date comes from several community and vendor
  notices, not from OpenAI's own page, and it was not confirmed whether the shutdown happened on that date.
  Either way nothing in this tool needs a conversation, so it now makes one Responses request per article.
* `requests` (replaced by `httpx`). The old `requirements.txt` pinned 18 packages, only three of them direct
  (`openai`, `python-dotenv`, `requests`); `uv.lock` now records the transitive ones.
