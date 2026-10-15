# Execute PRP Command

You are the **ORCHESTRATOR**. Execute the PRP at $ARGUMENTS following `agents/ORCHESTRATOR.md`.

## STEP 0: Load context
Read `agents/ORCHESTRATOR.md`, the PRP, `CLAUDE.md` and `INITIAL.md`. Create a task list with one task per phase and per agent.

## STEP 1: Phase 0 - Contracts (you, sequentially)
Write exactly what the PRP's CONTRACTS section specifies:
- `reviewlens/__init__.py`, `reviewlens/schemas.py`, `reviewlens/config.py`
- Stubs for every public function (`raise NotImplementedError`) in their final module paths, plus `__init__.py` in each package
- `requirements.txt`, `pyproject.toml`, `.env.example`

**Gate 0**: create/activate `.venv`, `pip install -r requirements.txt`, `python -c "import reviewlens.schemas, reviewlens.config"`.

## STEP 2: Phase 1 - CHAIN-AGENT ∥ DATA-AGENT
Dispatch **both in one response** (two Agent calls, `subagent_type: general-purpose`). Each prompt contains:

```
You are <AGENT>. Read agents/<agent>.md, the skills it lists, CLAUDE.md, and PRP section TASKS/<AGENT>.
Contracts in reviewlens/schemas.py and reviewlens/config.py are frozen: do not edit them.
Edit only the files you own. Replace the stubs in your files with real implementations.
Run your validation commands and return: files changed, validation output, open issues.
```

**Gate 1**: `ruff check reviewlens`, `python scripts/make_sample.py`, and the import checks from both agent files.

## STEP 3: Phase 2 - UI-AGENT ∥ TEST-AGENT
Dispatch both in one response, same prompt pattern.

**Gate 2**: `pytest -q` (offline, must pass with no API key), `ruff check .`

If a gate fails, send the exact error to the owning agent (SendMessage to continue it). Stop after 2 failed attempts and report.

## STEP 4: Phase 3 - Integration (you)
1. If `.env` has a key: `pytest -m live -q`. Otherwise mark it "skipped: no key".
2. Update `README.md` run instructions.
3. Walk the brief §1.8 checklist and record the evidence for each item.
4. Tell the user how to do the manual UI check: `streamlit run app.py` → upload `data/sample/reviews_week40_full.csv`.

## STEP 5: Final report
Use the format in `agents/ORCHESTRATOR.md` → "Final report". Be honest: list failing or skipped items as such.
