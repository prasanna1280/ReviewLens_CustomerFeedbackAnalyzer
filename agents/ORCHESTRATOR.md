# ORCHESTRATOR

> Coordinates the build of ReviewLens. Small project (2-3 day scope), so: 4 agents, 4 phases, contracts first.

---

## Agents

| Agent | Owns | Reads |
|-------|------|-------|
| ORCHESTRATOR (me) | Phase 0 contracts, integration, final report | `CLAUDE.md`, `INITIAL.md`, the PRP |
| CHAIN-AGENT | `reviewlens/llm.py`, `prompts.py`, `chains/` | `agents/chain-agent.md`, `skills/LANGCHAIN.md` |
| DATA-AGENT | `reviewlens/data/`, `report_render.py`, `data/sample/`, `scripts/make_sample.py` | `agents/data-agent.md`, `skills/DATA.md` |
| UI-AGENT | `app.py` | `agents/ui-agent.md`, `skills/STREAMLIT.md` |
| TEST-AGENT | `tests/`, checklist review | `agents/test-agent.md`, `skills/TESTING.md` |

---

## Phases

```
Phase 0  ORCHESTRATOR (sequential)   contracts: schemas.py, config.py, package skeleton,
                                     requirements.txt, pyproject.toml, .env.example
                                     ── Gate 0: pip install -r requirements.txt; python -c "import reviewlens.schemas"
Phase 1  CHAIN-AGENT ∥ DATA-AGENT    both code against Phase 0 contracts only
                                     ── Gate 1: ruff check reviewlens; python scripts/make_sample.py
Phase 2  UI-AGENT ∥ TEST-AGENT       UI wires Phase 1 functions; tests cover Phase 1 modules
                                     ── Gate 2: pytest -q (offline); ruff check .
Phase 3  ORCHESTRATOR                integration: live smoke (if .env present), done-checklist review
                                     ── Final gate: see below
```

Why contracts first: `schemas.py` (allowed values, `ReviewAnalysis`, `WeeklyInsights`) and `config.py` (`settings`) are imported by every other module. Freezing them in Phase 0 lets Phases 1 and 2 run in parallel without naming conflicts.

### Function signatures frozen in Phase 0 (agents must not change them)

```python
# chains/classify.py
build_classify_chain(llm) -> Runnable
classify_reviews(chain, rows: list[dict], max_concurrency: int, max_retries: int, on_progress=None) -> list[ReviewAnalysis | Exception]
# chains/report.py
build_report_chain(llm) -> Runnable
generate_insights(chain, df_ok: pd.DataFrame, stats: dict) -> WeeklyInsights   # returns SANITIZED insights
# data/loader.py
load_reviews(file) -> LoadResult            # raises InvalidCSVError
enrich(df, results) -> pd.DataFrame
# data/aggregate.py
compute_stats(df) -> dict
# report_render.py
render_report(stats: dict, insights: WeeklyInsights) -> str
# data/export.py
to_excel_csv(df) -> bytes
```

Write these as stubs (`raise NotImplementedError`) in Phase 0 so imports work from the start.

---

## Dispatch format

```yaml
TO: chain-agent
TASK: Implement classify + report chains
READ: [agents/chain-agent.md, skills/LANGCHAIN.md, CLAUDE.md]
CONTRACTS: reviewlens/schemas.py, reviewlens/config.py (do not edit)
OUTPUTS: [reviewlens/llm.py, reviewlens/prompts.py, reviewlens/chains/classify.py, reviewlens/chains/report.py]
VALIDATION: [ruff check reviewlens/chains, python -c "from reviewlens.chains.classify import classify_reviews"]
```

Run parallel phases as multiple Agent calls in **one** response.

---

## Conflict rules

- A contract needs changing → only the ORCHESTRATOR edits it, then notifies all agents.
- Allowed-value lists exist only in `schemas.py`. Any duplicate gets removed.
- An agent must not edit files outside its "Owns" column.

## Error recovery

1. Read the failing gate output.
2. Route the fix to the owning agent with the exact error.
3. After 2 failed fix attempts, stop and report to the user with the error and what was tried.

---

## Final gate

```bash
ruff check .
pytest -q
pytest -m live -q          # only if .env has a key; otherwise report "skipped: no key"
streamlit run app.py       # manual: upload reviews_week40_full.csv, check §1.8 items
```

## Final report

```
REVIEWLENS BUILD
Status: SUCCESS | PARTIAL
Files: <n>   Tests: <passed>/<total> (live: ran|skipped)
Done checklist (brief §1.8):
  [x] 200+ rows ...            evidence: test_classify::test_250_rows
  [x] 6 fields, allowed values evidence: ...
  ...
Run: streamlit run app.py
```
