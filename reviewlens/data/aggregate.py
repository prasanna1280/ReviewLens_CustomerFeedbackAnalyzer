"""Statistics computed in pandas - the only source of numbers in the UI and report."""

import pandas as pd

from reviewlens.data.loader import STATUS_OK
from reviewlens.schemas import CATEGORIES, LANGUAGES, SENTIMENTS, URGENCIES


def counts(series: pd.Series, allowed: tuple[str, ...]) -> dict[str, int]:
    """Value counts in allowed order, zero-filled."""
    vc = series.value_counts().reindex(list(allowed), fill_value=0)
    return {k: int(v) for k, v in vc.items()}


def pct(count_map: dict[str, int], total: int) -> dict[str, float]:
    """Percentages over total (0 when total is 0)."""
    return {k: (100.0 * v / total if total else 0.0) for k, v in count_map.items()}


def compute_stats(df: pd.DataFrame) -> dict:
    """Counts and percentages by sentiment, category, urgency, platform and language."""
    ok = df[df["status"] == STATUS_OK]
    analysed = len(ok)
    sentiment_counts = counts(ok["sentiment"], SENTIMENTS)
    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    ratings = pd.to_numeric(df["rating"], errors="coerce").dropna()
    return {
        "total": len(df),
        "analysed": analysed,
        "needs_review": len(df) - analysed,
        "date_from": dates.min().date() if not dates.empty else None,
        "date_to": dates.max().date() if not dates.empty else None,
        "sentiment_counts": sentiment_counts,
        "sentiment_pct": pct(sentiment_counts, analysed),
        "category_counts": counts(ok["category"], CATEGORIES),
        "urgency_counts": counts(ok["urgency"], URGENCIES),
        "language_counts": counts(ok["language"], LANGUAGES),
        "platform_counts": {str(k): int(v) for k, v in ok["platform"].value_counts().items()},
        "urgent": int((ok["urgency"] == "high").sum()),
        "negative_by_category": counts(ok.loc[ok["sentiment"] == "negative", "category"], CATEGORIES),
        "avg_rating": round(float(ratings.mean()), 2) if not ratings.empty else None,
    }
