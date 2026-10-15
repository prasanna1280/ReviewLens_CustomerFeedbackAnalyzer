# Testing Skill

> pytest. Offline by default with a fake LLM; real-model tests are opt-in with `-m live`.

---

## Setup

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["live: calls a real LLM (needs .env); run with -m live"]
addopts = "-m 'not live'"

[tool.ruff]
line-length = 110
```

---

## Faking the LLM

Chains take the model as a parameter, so tests can bypass providers entirely. The cleanest fake replaces the *whole structured chain* with a `RunnableLambda`:

```python
# tests/conftest.py
import pytest
from langchain_core.runnables import RunnableLambda
from reviewlens.schemas import ReviewAnalysis


def make_analysis(**over) -> ReviewAnalysis:
    base = dict(
        sentiment="negative",
        category="delivery",
        urgency="high",
        language="English",
        summary="Order arrived late and cold.",
        suggested_reply="Sorry about that.",
    )
    return ReviewAnalysis(**{**base, **over})


@pytest.fixture
def fake_chain():
    return RunnableLambda(lambda row: make_analysis())


@pytest.fixture
def flaky_chain():
    """Fails the first call for each review_text, then succeeds: exercises retry."""
    seen: set[str] = set()

    def run(row):
        if row["review_text"] not in seen:
            seen.add(row["review_text"])
            raise ValueError("category 'service' not in allowed list")
        return make_analysis()

    return RunnableLambda(run)


@pytest.fixture
def broken_chain():
    def run(row):
        raise ValueError("invalid output")

    return RunnableLambda(run)
```

`RunnableLambda.batch(..., return_exceptions=True)` behaves like the real chain, so `classify_reviews` is tested exactly as it runs in production.

---

## Must-have tests (mapped to brief §1.8)

| Test file | Covers |
|-----------|--------|
| `test_loader.py` | missing column → `InvalidCSVError`; empty text dropped + logged; duplicate id dropped; BOM file loads; Tamil text round-trips |
| `test_classify.py` | happy path; `flaky_chain` → all ok after retry; `broken_chain` → all `needs_review`, no exception escapes; 250-row input completes |
| `test_schemas.py` | invalid category / sentiment / urgency → `ValidationError` |
| `test_aggregate.py` | every count equals `df.value_counts()`; % over analysed rows; zero-filled categories |
| `test_report.py` | hallucinated ids dropped; theme count = len(valid ids); rendered text contains pandas numbers; exactly 3 action items |
| `test_export.py` | bytes start with UTF-8 BOM; re-read equals original; Tamil preserved |
| `test_config.py` | settings read from env; no key literal anywhere in `reviewlens/` (grep for `sk-`, `AIza`) |
| `test_live.py` (`@pytest.mark.live`) | brief rows R-1041..R-1043 → R-1042 is negative/delivery/high; R-1043 language Tanglish, summary English |

---

## Commands

```bash
pytest -q                 # offline
pytest -m live -q         # real model, costs a few calls
pytest --cov=reviewlens   # optional coverage
ruff check .
```

## Manual check (UI)

1. `streamlit run app.py` → upload `data/sample/reviews_week40_full.csv` → Analyse.
2. Toggle HIGH urgency and confirm only `high` rows show.
3. Download the CSV, open it in Excel, and check the Tamil text displays correctly.
4. Compare the report's percentages with the dashboard KPI row. They must be identical.
