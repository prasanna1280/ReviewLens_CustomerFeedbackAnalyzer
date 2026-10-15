# PRP: ReviewLens - Customer Feedback Analyzer

> Implementation blueprint, kept in sync with the build. Source: [`INITIAL.md`](../INITIAL.md) → [`docs/USE_CASE.md`](../docs/USE_CASE.md).

## METADATA

| Field | Value |
|-------|-------|
| Product | ReviewLens - Customer Feedback Analyzer |
| Type | Single-tenant GenAI tool (Streamlit), fixed LangChain pipeline |
| Version | 2.0 (v1.0 core · v1.1 enterprise UI · v2.0 history, trends, native replies, Monday email, roles) |
| Created | 2026-10-15 |
| Complexity | Medium |
| LLM | OpenAI `gpt-5.4-mini` via `init_chat_model` (swappable through `LLM_MODEL`) |
| Status | ✅ Built · ✅ Tested · ✅ Deployed at https://reviewlens.prasanna.digital |

---

## GOAL

Turn 200-500 weekly reviews (English / Tamil / Tanglish, from Google, Zomato, Swiggy and Amazon) into tagged, prioritised insights and a weekly report a manager can act on in five minutes.
**Done = every item of brief §1.8 checked** (see trace below).

---

## CONTEXT & GOTCHAS

- `llm.with_structured_output(PydanticModel)` (langchain-openai 1.7, default `method="json_schema"`) returns the Pydantic object. `Literal` fields enforce the allowed lists, and a violation raises, which triggers our retry.
- OpenAI strict JSON schema: every field must be required → `Theme.note` is a required `str` (empty allowed). Length limits (max 3 themes, exactly 3 actions) are enforced in Python (`sanitize_insights`), not in the schema.
- `Runnable.batch(..., config={"max_concurrency": n}, return_exceptions=True)` isolates per-row failures.
- `gpt-5.4-mini` accepts `temperature=0` (verified live).
- pandas 3.x: read with `dtype=str, keep_default_na=False`, then coerce `rating`/`date` explicitly.
- Streamlit `UploadedFile.read()` exhausts the buffer across reruns, so use `getvalue()`.
- Excel needs a BOM (`utf-8-sig`) to show Tamil script correctly.
- VPS already runs Traefik (host network, `websecure`, resolver `letsencrypt`), so we join via labels and publish no port.

---

## CONTRACTS (Phase 0)

| Module | Public API |
|--------|-----------|
| `reviewlens/schemas.py` | `Sentiment`, `Category`, `Urgency`, `Language` Literals + tuples; `ReviewAnalysis`, `Theme`, `WeeklyInsights`; `ANALYSIS_FIELDS` |
| `reviewlens/config.py` | `settings` (`llm_model`, `max_concurrency`, `max_retries`, `chunk_size`), `load_settings()` |
| `reviewlens/llm.py` | `get_llm(model=None) -> BaseChatModel`, `LLMConfigError` |
| `reviewlens/chains/classify.py` | `build_classify_chain(llm)`, `classify_reviews(chain, rows, max_concurrency, max_retries, on_progress=None, chunk_size=25)` |
| `reviewlens/chains/report.py` | `build_report_chain(llm)`, `generate_insights(chain, df_ok, stats)`, `sanitize_insights(insights, known_ids)` |
| `reviewlens/data/loader.py` | `load_reviews(src) -> LoadResult`, `InvalidCSVError`, `to_chain_inputs(df)`, `enrich(df, results)` |
| `reviewlens/data/aggregate.py` | `compute_stats(df) -> dict` |
| `reviewlens/data/export.py` | `to_excel_csv(df) -> bytes` |
| `reviewlens/report_render.py` | `render_report(stats, insights) -> str`, `date_range_label(stats)` |
| `reviewlens/ui/` | `charts.py` (Altair, fixed palette), `components.py` (CSS, header, KPI row, urgent card, report view) |

---

## TASKS (as built)

### CHAIN-AGENT
1. `prompts.py`: classify system prompt with category guide + urgency rules + "summary always English"; 3 few-shot pairs (English, Tanglish, Tamil). Report prompt asks for themes with `review_ids` and forbids numbers.
2. `classify.py`: chunked (25) `batch()` with bounded concurrency. Failed rows are re-batched up to `MAX_RETRIES`, then returned as `Exception` (→ `needs_review`).
3. `report.py`: compact one-line-per-review input + pandas stats. Output is sanitized (unknown/duplicate ids dropped, empty themes removed, top 3 by evidence).

### DATA-AGENT
1. `loader.py`: column check (case/space tolerant), drop empty text / missing id / duplicate id with reasons; keep bad rating/date rows with warnings; BOM + cp1252 fallback.
2. `aggregate.py`: zero-filled counts in allowed order, % over analysed rows, urgent count, date range.
3. `report_render.py`: brief §1.6 Output B layout; theme count = `len(valid ids)`.
4. `scripts/make_sample.py`: deterministic 233-row week (230 valid + 2 empty + 1 duplicate).

### UI-AGENT (v1.1 enterprise redesign)
- Theme: navy sidebar, Inter font, light canvas, bordered cards (`.streamlit/config.toml`).
- Password screen (when `APP_PASSWORD` set), sidebar workspace (upload, sample toggle, CSV template, config, sign-out).
- Pre-run: validation summary, data preview, row cap. Run: `st.status` with progress.
- Role-oriented tabs:
  - **Overview** (operations manager): sentiment donut, category × sentiment, daily trend, platforms, urgency, languages
  - **Urgent queue** (support team): HIGH-urgency cards with original text, English summary, copyable reply, "Handled" tracker, category pills, CSV export
  - **Weekly report** (business owner): KPI line, complaints table, praise badges, 3 action items, .txt download
  - **All reviews**: search + 5 filters, configured columns, full and filtered Excel export
- Results cached in `st.session_state`. Widgets never re-call the LLM.

### TEST-AGENT
`tests/` contains 23 offline tests (fake `RunnableLambda`) + 4 live tests (`-m live`).

### DEVOPS
`Dockerfile` (python:3.12-slim, non-root, healthcheck), `docker-compose.yml` (local, 127.0.0.1:8501), `docker-compose.prod.yml` (Traefik labels, HSTS headers, no host port).

---

## PHASES & GATES

| Phase | Work | Gate | Result |
|-------|------|------|--------|
| 0 | Contracts, requirements, pyproject, .env.example | `import reviewlens.schemas` | ✅ |
| 1 | Chains ∥ data + sample generator | `ruff check`; `make_sample.py` | ✅ |
| 2 | UI ∥ tests | `pytest -q` (23 passed); headless `AppTest` | ✅ |
| 3 | Live + integration | `pytest -m live` (4 passed); 230-row run: 64 s classify, 6 s report, 0 needs_review | ✅ |
| 4 | Deploy | GitHub push → VPS `docker compose ... up -d --build` → HTTPS 200, Let's Encrypt cert | ✅ |

---

## DONE-CHECKLIST TRACE (brief §1.8)

| Item | Implemented in | Verified by |
|------|----------------|-------------|
| 200+ row CSV without crash/timeout | chunked batch, bounded concurrency, per-row isolation | `test_classify::test_250_rows...`; live 230-row run |
| All 6 fields, allowed values only | `ReviewAnalysis` Literals + retry + `needs_review` | `test_full_sample_every_row_has_all_six_fields`, `test_schema_rejects_*` |
| Tamil/Tanglish → correct English summary | prompt rules + few-shot | `test_live::test_tanglish_gets_english_summary`; manual review of live output |
| Report numbers match table (pandas) | `compute_stats`, `sanitize_insights`, `render_report` | `test_stats_match_pandas_value_counts`, `test_report_numbers_come_from_stats` |
| HIGH filter + Excel-safe CSV | Urgent queue tab, Reviews filters, `to_excel_csv` | `test_export_is_excel_safe_and_round_trips`; AppTest filter check |
| API key from .env, never hard-coded | `config.py` + python-dotenv; `.env` gitignored; VPS `.env` chmod 600 | `test_no_hardcoded_api_keys` |

---

## v2 - STRETCH GOALS + ROLE WORKSPACES

| Feature | Design | Files | Verified by |
|---------|--------|-------|-------------|
| Week history | SQLite (`weeks`, `reviews`, `settings`, `email_log`), WAL, connection per call; Docker named volume `/app/storage` | `storage.py`, `pipeline.py` | `test_storage_trends.py` |
| Trend arrows | `Delta` (change, arrow, good/bad by direction) vs previous stored ISO week; KPI deltas, report "VS WEEK n" section, multi-week sentiment/urgent/heatmap charts; trend text fed to report chain so actions react to movement | `trends.py`, `report_render.py`, `ui/charts.py` | `test_trend_deltas_and_text`, `test_weekly_series` |
| Same-language replies | `reply_english` generated first, `suggested_reply` rendered in review language/script; identical non-English reply = soft failure → retried, then accepted | `schemas.py`, `prompts.py`, `chains/classify.py` | `test_reply_in_wrong_language_is_retried_then_accepted`; live check: first-attempt Tanglish failures 43% → 3% |
| Monday email | HTML (KPIs + arrows, complaint movers, themes, actions, CTA) + plain text + enriched CSV; `scheduler` container ticks every 60 s, fires once per day on configured weekday/time (Asia/Kolkata); reminder if latest week already sent; all sends logged | `emailer.py`, `scheduler.py`, `docker-compose.yml` | `test_roles_email.py` (fake SMTP) |
| Role workspaces | Owner / Manager / Support → tabs + permission set; per-role PIN (fallback `APP_PASSWORD`); storage writes whitelist fields per role | `roles.py`, `app.py` | `test_permission_matrix`, `test_role_pins`, `test_app_ui.py` (headless per role) |
| Multi-week samples | W38-W41 in EN/Tamil/Tanglish with a trend story; W38-W40 pre-analysed (`history/`) and auto-seeded into an empty DB | `scripts/make_sample.py`, `scripts/seed_history.py` | `test_demo_history_imports` |

## OUT OF SCOPE / BACKLOG

- Per-user accounts (Google OAuth via `st.login` + email allowlist) if access must be audited per person.
- Auto-ingest reviews from platform APIs instead of CSV upload.
- Multi-outlet support (outlet column, per-outlet trends).
