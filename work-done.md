# Work done on news-summarizer (branch `chore/modernize`)

Local commit only; nothing was pushed. This was not a clean-up of a working tool: the original could not run,
so it was rebuilt as a small package with the same purpose.

## What was there

Three commits (2024-02-06 to 2024-02-13) and five files: `summarizer.py` (275 lines), an 18-line
`requirements.txt`, a two-line README, `LICENSE` (MIT) and `.gitignore`. No tests.

Reading `summarizer.py` against the OpenAI SDK, it **could not have worked**:

| Where | Problem |
|---|---|
| `summarize_news` | called `client.summarize(...)`, which does not exist on the OpenAI client |
| `AssistantManager.__init__` | `client.beta.assistant.retrieve` and `client.beta.assistant.thread.retrieve`: neither attribute exists (`assistants`, `threads`) |
| `create_assistant` | `create(..., models=...)`: the argument is `model` |
| `wait_for_completion` | polled forever when a run ended `failed`, `cancelled` or `expired` |
| `call_required_functions` | resubmitted the tool outputs inside the loop, after every call, instead of once |
| `process_messages` | logged every message of the thread at INFO under the label "SUMMARY" (noise, not a failure) |
| `call_required_functions` | `raise ValueError("Unknown function: %s", name)` never formats the name |
| `get_news` | built the URL by hand: the topic was not URL-encoded, and the **API key was in the query string**, where the `except` branch then logged it (`requests` puts the URL in its exception text) |
| `get_news` | no timeout; indexed `article["title"]` etc. directly, so an article lacking a field would raise `KeyError` and the broad `except` would discard every article |
| module level | `load_dotenv()`, `logging.basicConfig()` and `OpenAI()` ran on import, so importing the file without a key raised |
| `main()` | only fetched "Crypto" news and logged the first article; the summarizing code was never called |
| model | `gpt-3.5-turbo-16k`, an old model name |
| whole design | built on the **Assistants API**, which OpenAI deprecated and announced to shut down on August 26, 2026 (from community and vendor notices; not confirmed on OpenAI's own page, and not confirmed that the date held) |

## What changed

| File | Change |
|---|---|
| `summarizer.py`, `requirements.txt` | removed (the old code stays in git history) |
| `src/news_summarizer/config.py` | settings from the environment; missing or invalid values are reported by name; the two keys are excluded from `repr` |
| `src/news_summarizer/news.py` | NewsAPI client: key in the `X-Api-Key` header, topic passed as a parameter, timeout, tolerant parsing, `[Removed]` articles dropped, NewsAPI's `[+N chars]` marker removed, errors that never contain the key or the URL |
| `src/news_summarizer/summarizer.py` | one request per article on the **Responses API** (`responses.create`); a failure on one article is recorded and the rest continue; a rejected key stops the run after one request |
| `src/news_summarizer/pipeline.py`, `cli.py`, `__main__.py` | `summarize_topic`, and the `news-summarizer` command (text or `--json`, exit codes 0/1/2/3, control, format and bidi characters removed from printed text, escaped in JSON) |
| `pyproject.toml`, `uv.lock`, `.python-version` | uv project on Python 3.13; 3 direct dependencies (`openai`, `httpx`, `python-dotenv`) instead of 18 pins |
| `tests/` | 95 tests (below) |
| `.env.example`, `.gitignore` | demo values for every variable (a test keeps the file complete); `.env.*` and `.ruff_cache` ignored |
| `.github/workflows/ci.yml` | lint, format check, tests |
| `README.md`, `VERSIONS.md`, `work-done.md` | written |

### Behaviour that is not in the original

The Assistants flow with the `get_news` tool call (the model deciding when to fetch news) is gone. Replacing it
with a plain "fetch, then summarize each article" pipeline keeps the purpose (summaries of news about a topic)
and removes the polling loop; the cost is that the model no longer chooses what to search for.

## Verified (commands actually run)

| Check | Result |
|---|---|
| `uv run pytest -q --cov` | 95 passed; coverage 99 % (283 statements, 60 branches; the 3 missed lines are `__main__.py`, run only in a subprocess) |
| `ruff check .`, `ruff format --check .` | pass, with rules `E F I B UP SIM S BLE RUF` |
| mutation check | 30 defects reintroduced one at a time (key in the URL, `[Removed]` kept, key not scrubbed, no fatal stop on a bad key, control characters not stripped, wrong exit codes, ...): the suite failed for all 30; sources restored afterwards. A 28th check (an undocumented variable) confirmed the `.env.example` test |
| end-to-end tests | real `httpx` and OpenAI SDK clients against local fake NewsAPI and OpenAI servers, real services blocked by a dead proxy |
| the installed `news-summarizer` command, as a separate process | text and `--json` output, a refused article (exit 1), a bad `-n` (exit 2) |
| secret scan of all 3 commits and of the tree being committed | nothing found (count-only scan: OpenAI-style keys, private keys, URLs with passwords, key-like literals, 32-hex strings) |

## Follow-up: automated security review

A review of the first commit found the terminal sanitizer too narrow: it dropped only characters below U+0020, so
C1 controls (U+0080 to U+009F, which some terminals treat as escape introducers), bidi overrides and the invisible
"tag" characters used to hide text got through. Also, error text from NewsAPI reached stderr uncleaned, and
`--json` (written with `ensure_ascii=False`) printed those characters raw. All three are fixed in the second commit:
the sanitizer now drops every character whose Unicode category starts with `C`, the JSON output escapes them (it
still round-trips to the original text), and error messages are cleaned. Three more reintroduced defects confirm it.
Dropping category `Cf` also removes the zero width joiner, so some multi-part emoji print as separate emoji.

## Not verified

* **No live NewsAPI or OpenAI call was made.** There were no keys; everything used demo values and local servers.
  The request shapes follow the NewsAPI and OpenAI SDK documentation, and the fake OpenAI response was validated
  against the SDK's own `Response` model.
* The default model `gpt-5.5` comes from the SDK README's examples; not checked against any account.
* GitHub Actions has not run (the same commands were run locally).
* NewsAPI's free plan has its own limits on what it returns and where it may be used; not checked here.

## Needs you

* Nothing to rotate: no secret was ever committed.
* Put real keys in `.env` (copy `.env.example`) before first use.
* The old script's behaviour is gone on purpose. If you want the model to decide what to search for, that is a
  function-calling feature on the Responses API and would be a separate piece of work.
