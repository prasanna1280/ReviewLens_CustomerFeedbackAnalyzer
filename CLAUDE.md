# CLAUDE.md - ReviewLens Project Rules

> Read automatically by Claude Code. Scope lives in `docs/USE_CASE.md` (brief) and `INITIAL.md` (product definition).

## Project overview

ReviewLens is a Streamlit app that runs a **fixed LangChain pipeline** over a weekly CSV of customer reviews:
validate → classify each review (structured output, batched) → aggregate in pandas → weekly report chain → dashboard + CSV export.

It's a Gen AI track project: we design the steps and the LLM does each step. No agents or tool-calling loops, and no API server. Analysed weeks are stored in a small SQLite database (week history, edits, email log); a separate scheduler container emails the weekly report. Access is by role workspace (Business Owner / Operations Manager / Customer Support) with optional per-role PINs - there are no user accounts.

## Project structure

```
ReviewLens_CustomerFeedbackAnalyzer/
├── app.py                       # Streamlit entry point (UI only, no business logic)
├── .streamlit/config.toml       # theme (navy sidebar, Inter) + server settings
├── reviewlens/
│   ├── __init__.py
│   ├── config.py                # Settings from .env (LLM_MODEL, MAX_CONCURRENCY, MAX_RETRIES, BATCH_SIZE)
│   ├── schemas.py               # Pydantic models + Literal enums (single source of allowed values)
│   ├── llm.py                   # get_llm(): init_chat_model(settings.llm_model, temperature=0)
│   ├── prompts.py               # All ChatPromptTemplates
│   ├── chains/
│   │   ├── classify.py          # map: per-review chain, batch + retry + needs_review
│   │   └── report.py            # reduce: WeeklyInsights chain
│   ├── data/
│   │   ├── loader.py            # read + validate CSV
│   │   ├── aggregate.py         # pandas stats (the ONLY source of numbers)
│   │   └── export.py            # enriched CSV bytes (utf-8-sig)
│   ├── report_render.py         # stats + WeeklyInsights (+ previous week) → report text
│   ├── storage.py               # SQLite: weeks, reviews (edits, handled), settings, email_log
│   ├── pipeline.py              # analyse_and_save, regenerate_report, classify_one, demo history import
│   ├── trends.py                # week-over-week Delta maths + multi-week series (pandas only)
│   ├── roles.py                 # role definitions, permission matrix, PIN check
│   ├── emailer.py               # weekly email (HTML + text + CSV) over SMTP, send + log
│   ├── scheduler.py             # long-running Monday job (own container)
│   └── ui/                      # Streamlit presentation only: charts.py (Altair palette), components.py
├── data/sample/                 # weeks 38-41 raw CSVs (EN/Tamil/Tanglish) + history/ (pre-analysed W38-W40)
├── scripts/                     # make_sample.py (raw weeks), seed_history.py (analyse -> history/)
├── tests/                       # pytest; LLM faked unless -m live
├── docs/USE_CASE.md             # source brief
├── PRPs/  agents/  skills/  .claude/commands/
├── requirements.txt
├── .env.example                 # committed; .env is gitignored
└── README.md
```

## Non-negotiable rules

1. **Numbers come from pandas.** The LLM never produces a count or percentage that reaches the UI or report. The report chain returns `review_ids` per theme, and Python counts them after discarding unknown ids.
2. **Allowed values live in `schemas.py` only.** Prompts, charts and tests import them from there. Never duplicate the lists.
3. **Structured output only.** Every LLM call is `prompt | llm.with_structured_output(PydanticModel)`. Don't parse JSON by hand from free text.
4. **One bad review never breaks the batch.** Use `return_exceptions=True`, retry failed rows up to `MAX_RETRIES`, then set `status="needs_review"` with the error message. Never drop a row silently.
5. **Bounded concurrency.** Always pass `config={"max_concurrency": settings.max_concurrency}` to `.batch()`.
6. **Provider-agnostic.** Only `reviewlens/llm.py` knows which provider is in use. Chains receive the model through a parameter (dependency injection), so tests can pass a fake.
7. **Secrets.** Keys are read from `.env` via python-dotenv. Never hard-code keys, never log them, never commit `.env`.
8. **Summaries are always English**, whatever the review language. Replies are English in the MVP (same-language replies is a stretch goal).
9. **`temperature=0`** for classification. The report chain may use the same model.
10. **UI holds no logic.** `app.py` calls `reviewlens` functions and caches results in `st.session_state`. Widget interactions must never re-trigger LLM calls.
11. **Excel-safe export.** Write the CSV with `encoding="utf-8-sig"` so Tamil script survives a double-click open in Excel.
12. **Replies in the customer's language.** `reply_english` is written first, `suggested_reply` renders it in the review's language/script. A Tamil/Tanglish reply identical to the English one is retried, then accepted.
13. **Permissions live in `roles.py`.** The UI checks `R.<PERM> in role.perms`; storage writes take an `allowed` field whitelist so a role can never write fields it may not edit.
14. **Trends compare stored weeks only** (previous ISO week in the database), computed by `trends.py`.

## Code standards

- Type hints on all functions. Docstrings on public functions (one line is fine).
- Use the `logging` module, not `print`.
- Pydantic v2 idioms (`model_dump`, `field_validator`).
- Keep functions pure where possible (df in, df out) so they're testable without Streamlit.
- Match the style of surrounding code. Don't add frameworks that `INITIAL.md` doesn't list.

## Environment variables (`.env`)

```env
LLM_MODEL=openai:<model>          # or google_genai:<model> / anthropic:<model>
OPENAI_API_KEY=                   # set the key for the provider you chose
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=
MAX_CONCURRENCY=5
MAX_RETRIES=2
```

## Commands

```bash
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
streamlit run app.py
pytest                       # offline, fake LLM
pytest -m live               # real LLM calls, needs .env
ruff check . && ruff format .
```

## Testing rules

- Unit tests must pass with **no API key and no network**. Fake the model with a `RunnableLambda` that returns Pydantic objects (see `skills/TESTING.md`).
- Live tests are marked `@pytest.mark.live` and skipped unless selected.
- Every done-checklist item in `docs/USE_CASE.md` §1.8 has at least one test or a documented manual check.

## Skills reference

| Task | Read |
|------|------|
| Prompts, chains, structured output, batching, retry | `skills/LANGCHAIN.md` |
| CSV validation, aggregation, export | `skills/DATA.md` |
| Streamlit UI, charts, session state | `skills/STREAMLIT.md` |
| Tests and fakes | `skills/TESTING.md` |

## Agents

`agents/ORCHESTRATOR.md` coordinates CHAIN-AGENT, DATA-AGENT, UI-AGENT and TEST-AGENT. See `agents/`.

## Commits

`feat(chain): ...`, `feat(data): ...`, `feat(ui): ...`, `test: ...`, `docs: ...`, `chore: ...`
