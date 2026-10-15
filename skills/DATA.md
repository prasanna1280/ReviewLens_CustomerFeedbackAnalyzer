# Data Skill

> pandas validation, aggregation and Excel-safe export. Every number shown to the user comes from here.

---

## Load + validate

```python
# reviewlens/data/loader.py
from dataclasses import dataclass, field
import pandas as pd

REQUIRED_COLUMNS = ["review_id", "date", "platform", "rating", "review_text"]


class InvalidCSVError(ValueError):
    """Raised when the CSV cannot be used at all (e.g. missing columns)."""


@dataclass
class LoadResult:
    df: pd.DataFrame
    dropped: list[dict] = field(default_factory=list)  # {"review_id", "reason"}


def load_reviews(file) -> LoadResult:
    """Read a reviews CSV and return clean rows plus a log of dropped rows."""
    df = pd.read_csv(file, dtype={"review_id": str}, encoding="utf-8-sig")
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise InvalidCSVError(f"Missing required column(s): {', '.join(missing)}")
    ...
```

Validation rules, in order. Each one records dropped rows with a reason:

1. Strip whitespace on string columns.
2. Drop rows where `review_text` is empty or NaN → reason `empty review_text`.
3. Drop duplicate `review_id`, keeping the first → reason `duplicate review_id`.
4. `rating` → `pd.to_numeric(errors="coerce")`. Values outside 1-5 or NaN are **kept** with `rating=NA`, because the text still has value. Only log them.
5. `date` → `pd.to_datetime(errors="coerce")`. Keep NaT rows, but leave them out of the report's date range.
6. Raise `InvalidCSVError` if 0 rows remain.

Read with `encoding="utf-8-sig"` so files saved from Excel (which adds a BOM) load cleanly. If that fails with `UnicodeDecodeError`, retry with `cp1252`.

---

## Enrich

```python
ANALYSIS_COLUMNS = ["sentiment", "category", "urgency", "language", "summary", "suggested_reply"]


def enrich(df: pd.DataFrame, results: list) -> pd.DataFrame:
    """Join per-row LLM results onto the input; failures become status='needs_review'."""
```

- `ReviewAnalysis` → `model_dump()` columns, `status="ok"`, `error=""`
- `Exception` → analysis columns empty, `status="needs_review"`, `error=str(exc)[:200]`

Column order: input columns, then `ANALYSIS_COLUMNS`, then `status`, then `error`.

---

## Aggregate (the only source of numbers)

```python
# reviewlens/data/aggregate.py
def compute_stats(df: pd.DataFrame) -> dict:
    ok = df[df.status == "ok"]
    total = len(df)
    return {
        "total": total,
        "analysed": len(ok),
        "needs_review": total - len(ok),
        "date_from": df.date.min(),
        "date_to": df.date.max(),
        "sentiment_pct": pct(ok.sentiment, SENTIMENTS),  # dict, every allowed key present (0 if absent)
        "sentiment_counts": counts(ok.sentiment, SENTIMENTS),
        "category_counts": counts(ok.category, CATEGORIES),
        "urgency_counts": counts(ok.urgency, URGENCIES),
        "platform_counts": ok.platform.value_counts().to_dict(),
        "language_counts": counts(ok.language, LANGUAGES),
        "urgent": int((ok.urgency == "high").sum()),
    }
```

- Percentages are calculated over **analysed** rows. Round to whole numbers for display only, and keep the raw counts.
- Use `value_counts().reindex(ALLOWED, fill_value=0)` so charts always show every category in a stable order.

---

## Report rendering

`reviewlens/report_render.py` takes `stats` and the sanitized `WeeklyInsights` and produces the exact §1.6 Output B layout:

```
WEEKLY FEEDBACK REPORT  |  29 Sep to 5 Oct 2026
Total reviews: 248   Positive 61%   Neutral 14%   Negative 25%
TOP 3 COMPLAINTS
  1. Late delivery ............ 34 reviews  (mostly Swiggy, 8pm to 10pm)
...
```

Theme counts are `len(valid_review_ids)`. Pad the theme labels with dots to a fixed width. If `needs_review > 0`, add a line `NOTE: N reviews could not be analysed and need manual review`.

---

## Export

```python
# reviewlens/data/export.py
def to_excel_csv(df: pd.DataFrame) -> bytes:
    """CSV bytes that open correctly in Excel, including Tamil script."""
    return df.to_csv(index=False).encode("utf-8-sig")
```

`utf-8-sig` adds a BOM. Without it, Excel guesses the encoding wrong and Tamil text becomes mojibake.

---

## Sample data

- `data/sample/reviews_week40.csv`: the 3 rows from the brief.
- `data/sample/reviews_week40_full.csv`: 200-250 synthetic rows. Generate them with a deterministic script (`scripts/make_sample.py`, `random.seed(40)`) from templates, so the file is reproducible. The rows should cover all 4 platforms, all 3 languages (Tamil script included), all 6 categories, and some high-urgency cases (food poisoning, wrong order, rude staff, refund). Include 2-3 rows with empty text and 1 duplicate id to exercise validation.
