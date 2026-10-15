# INITIAL.md - ReviewLens Product Definition

> Turn hundreds of raw customer reviews into tagged, prioritised insights and a weekly report a manager can act on in five minutes.

Source brief: [`docs/USE_CASE.md`](docs/USE_CASE.md). If this file and the brief disagree, the brief wins.

---

## PRODUCT

| | |
|---|---|
| **Name** | ReviewLens - Customer Feedback Analyzer |
| **Type** | Single-user GenAI tool (Streamlit web app), run locally |
| **Pattern** | Fixed LangChain pipeline (Gen AI track) - *not* an autonomous agent |
| **Users** | Operations manager, customer support team, business owner |
| **Input** | Weekly CSV of 200-500 reviews (Google, Zomato, Swiggy, Amazon) in English / Tamil / Tanglish |
| **Output** | Enriched review table + weekly insights report + dashboard + CSV export |

---

## TECH STACK

| Layer | Choice | Notes |
|-------|--------|-------|
| Language | Python 3.11+ | `venv` + `requirements.txt` |
| LLM framework | LangChain (`langchain-core`, LCEL) | `ChatPromptTemplate \| llm.with_structured_output(Model)` |
| LLM | Provider-agnostic via `init_chat_model("<provider>:<model>")` | Set in `.env` as `LLM_MODEL`; OpenAI, Gemini or Claude all work, with no code change |
| Validation | Pydantic v2 | `Literal` enums enforce the allowed lists |
| Data | pandas | All counts and percentages come from pandas, never the LLM |
| UI | Streamlit | Charts with Altair (ships with Streamlit, no extra dependency) |
| Config | python-dotenv | API keys only in `.env` |
| Quality | pytest, ruff | LLM is faked in unit tests; live tests are opt-in |

**Not in scope:** database, auth, REST API, React, Docker, payments. The brief doesn't call for any of them.

---

## PIPELINE

```
CSV upload ─► validate ─► classify (map, batched) ─► aggregate (pandas) ─► report (reduce) ─► dashboard + export
```

| # | Step | Module | Detail |
|---|------|--------|--------|
| 1 | Upload | `app.py` | `st.file_uploader`, CSV only |
| 2 | Validate | `reviewlens/data/loader.py` | Required columns present, strip whitespace, drop rows with empty `review_text`, de-duplicate `review_id`, coerce `rating` to int 1-5, parse `date`. Return a clean df + a list of what was dropped and why. |
| 3 | Classify | `reviewlens/chains/classify.py` | One chain per review, run with `chain.batch(inputs, config={"max_concurrency": N}, return_exceptions=True)`. Invalid or failed outputs are retried (`MAX_RETRIES`). Anything still failing gets `status="needs_review"`. |
| 4 | Aggregate | `reviewlens/data/aggregate.py` | Counts and percentages by sentiment, category, urgency, platform, language. Urgent count. Date range. |
| 5 | Report | `reviewlens/chains/report.py` | Reduce chain takes the compact per-review lines plus the pandas stats. It returns themes with the **review_ids** that support each one, so pandas does the counting. |
| 6 | Show + Export | `app.py`, `reviewlens/data/export.py` | Dashboard, HIGH-urgency filter, report text, CSV download (`utf-8-sig` so Tamil text opens correctly in Excel) |

---

## DATA CONTRACTS

### Input CSV

`review_id, date, platform, rating, review_text` (extra columns are kept and passed through).

### `ReviewAnalysis` (per review, structured LLM output)

| Field | Type / allowed values |
|-------|-----------------------|
| `sentiment` | `positive` \| `neutral` \| `negative` |
| `category` | `food_quality` \| `delivery` \| `price` \| `staff` \| `packaging` \| `app` |
| `urgency` | `low` \| `medium` \| `high` (high = health/safety, refund, abuse, wrong order) |
| `language` | `English` \| `Tamil` \| `Tanglish` |
| `summary` | One English sentence, always English even for Tamil or Tanglish input |
| `suggested_reply` | Polite, ready-to-post reply (English in the MVP) |

The enriched row = the input columns + the 6 fields + `status` (`ok` \| `needs_review`) + `error` (empty when ok).

### `WeeklyInsights` (report chain output)

- `top_complaints`: up to 3 × `{theme, review_ids[], note}`. `note` is an optional qualitative hint such as "mostly Swiggy, 8pm-10pm".
- `top_praise`: up to 3 × `{theme, review_ids[]}`
- `action_items`: exactly 3 strings

The final report text is rendered in Python using the format of brief §1.6 Output B. Every number in it (totals, %, theme counts as `len(valid ids)`, urgent count) comes from pandas. Review ids the LLM invents are dropped before counting.

---

## MVP SCOPE

### Must have (maps 1:1 to the brief's done checklist)
- [ ] Processes a 200+ row CSV without crashing or timing out (batched, bounded concurrency, per-row error isolation, progress bar)
- [ ] Every review has all 6 fields with allowed values, or is explicitly marked `needs_review` after retries
- [ ] Tamil and Tanglish reviews get a correct English summary
- [ ] Report numbers exactly match the table (computed in pandas)
- [ ] HIGH urgency filter works; enriched CSV opens correctly in Excel
- [ ] API key loaded from `.env`, never hard-coded

### Supporting deliverables
- [ ] `data/sample/reviews_week40.csv`: the 3 brief rows
- [ ] `data/sample/reviews_week40_full.csv`: 200+ synthetic rows across all platforms, languages, categories and urgencies (for the 200+ row check)
- [ ] README run instructions

### Stretch (post-MVP, only after all of the above pass)
- [ ] Week-over-week comparison with trend arrows (upload last week's enriched CSV)
- [ ] Replies in the same language as the review
- [ ] Email the weekly report automatically every Monday

---

## ACCEPTANCE CRITERIA

### Validation
- [ ] Missing a required column → clear error naming the column, no LLM calls made
- [ ] Empty `review_text` rows dropped and reported in the UI

### Classification
- [ ] Unit test: a fake LLM returns an invalid category once → retried → succeeds
- [ ] Unit test: a fake LLM always fails → row marked `needs_review`, pipeline continues
- [ ] Live smoke test (opt-in `-m live`) on the 3 brief rows matches the brief's sample output in spirit (R-1042 → negative / delivery / high)

### Report
- [ ] Unit test: report counts equal `df.value_counts()` for every figure
- [ ] Hallucinated review_ids are ignored

### UI
- [ ] Sentiment split chart, category chart, HIGH-urgency toggle, report panel, download button
- [ ] Results cached in `st.session_state`, so re-renders don't call the LLM again

### Quality
- [ ] `ruff check .` clean
- [ ] `pytest` passes without an API key

---

## BUILD ROLES

| Agent | Owns |
|-------|------|
| CHAIN-AGENT | `schemas.py`, `llm.py`, `prompts.py`, `chains/` |
| DATA-AGENT | `data/loader.py`, `data/aggregate.py`, `data/export.py`, `report_render.py`, sample CSVs |
| UI-AGENT | `app.py` (Streamlit) |
| TEST-AGENT | `tests/`, review against the done checklist |

---

# NEXT

```
/generate-prp INITIAL.md
/execute-prp PRPs/reviewlens-prp.md
```
