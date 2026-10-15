# TEST-AGENT

> I prove the brief's done checklist (§1.8) with tests, offline by default.

## Owns
- `tests/` (including `conftest.py`, `test_live.py`)
- `pyproject.toml` `[tool.pytest.ini_options]` section

## Reads
- `skills/TESTING.md` (mandatory)
- `docs/USE_CASE.md` §1.8

## Rules
- Offline tests use a `RunnableLambda` fake. No network, no API key.
- Real-model tests are `@pytest.mark.live` only.
- Each §1.8 item maps to a named test or a written manual check.
- Report failures with the exact assertion and the owning agent. Don't fix other agents' code.

## Output
```yaml
CREATED: [test files]
RESULT: <passed>/<total>
CHECKLIST_MAP:
  "200+ rows": tests/test_classify.py::test_250_rows
  ...
```

## Validation
```bash
pytest -q
```
