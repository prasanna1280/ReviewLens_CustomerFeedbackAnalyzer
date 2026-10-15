"""Week-over-week comparison. Pure pandas/dict maths - no LLM numbers."""

from dataclasses import dataclass

import pandas as pd

from reviewlens.schemas import CATEGORIES, SENTIMENTS

UP, DOWN, FLAT = "▲", "▼", "▬"


@dataclass(frozen=True)
class Delta:
    """One compared metric. `good` is True/False/None (None = no change or no direction)."""

    label: str
    current: float | None
    previous: float | None
    unit: str = ""  # "", "%", "pts", "★"
    higher_is_better: bool | None = True

    @property
    def change(self) -> float | None:
        if self.current is None or self.previous is None:
            return None
        return self.current - self.previous

    @property
    def arrow(self) -> str:
        c = self.change
        if c is None:
            return ""
        return UP if c > 0.05 else DOWN if c < -0.05 else FLAT

    @property
    def good(self) -> bool | None:
        c = self.change
        if c is None or abs(c) <= 0.05 or self.higher_is_better is None:
            return None
        return (c > 0) == self.higher_is_better

    def change_text(self) -> str:
        c = self.change
        if c is None:
            return "new"
        unit = " pts" if self.unit == "%" else self.unit
        fmt = f"{c:+.1f}" if self.unit in ("★",) else f"{c:+.0f}"
        return f"{self.arrow} {fmt}{unit}"


def compare(cur: dict, prev: dict | None) -> dict[str, Delta]:
    """Headline deltas between two compute_stats() results."""
    p = prev or {}
    pp = p.get("sentiment_pct", {})
    return {
        "reviews": Delta("Reviews", cur["analysed"], p.get("analysed"), higher_is_better=None),
        "positive": Delta("Positive", cur["sentiment_pct"]["positive"], pp.get("positive"), "%", True),
        "negative": Delta("Negative", cur["sentiment_pct"]["negative"], pp.get("negative"), "%", False),
        "urgent": Delta("Urgent", cur["urgent"], p.get("urgent"), "", False),
        "avg_rating": Delta("Avg rating", cur.get("avg_rating"), p.get("avg_rating"), "★", True),
    }


def category_complaint_deltas(cur: dict, prev: dict | None) -> list[Delta]:
    """Negative reviews per category vs last week, biggest movers first."""
    p = (prev or {}).get("negative_by_category", {})
    deltas = [Delta(c, cur["negative_by_category"][c], p.get(c) if prev else None, "", False) for c in CATEGORIES]
    return sorted(deltas, key=lambda d: abs(d.change or 0), reverse=True)


def trend_text(cur: dict, prev: dict | None, prev_label: str = "last week") -> str:
    """Plain-text summary used in the report prompt, report text and email."""
    if not prev:
        return "No previous week available."
    lines = [f"Compared with {prev_label}:"]
    for d in compare(cur, prev).values():
        lines.append(f"  {d.label}: {d.current:g} ({d.change_text()})" if d.current is not None else "")
    movers = [d for d in category_complaint_deltas(cur, prev) if d.change]
    if movers:
        lines.append(
            "  Complaints by category: " + ", ".join(f"{d.label} {d.current:g} ({d.change_text()})" for d in movers[:4])
        )
    return "\n".join(line for line in lines if line)


def weekly_series(all_reviews: pd.DataFrame) -> pd.DataFrame:
    """One row per week: % sentiment, urgent count, avg rating, negatives per category."""
    ok = all_reviews[all_reviews["status"] == "ok"]
    if ok.empty:
        return pd.DataFrame()
    g = ok.groupby("week_id")
    out = pd.DataFrame({"reviews": g.size()})
    for s in SENTIMENTS:
        out[f"{s}_pct"] = g["sentiment"].apply(lambda x, s=s: 100.0 * (x == s).mean())
    out["urgent"] = g["urgency"].apply(lambda x: int((x == "high").sum()))
    out["avg_rating"] = g["rating"].apply(lambda x: pd.to_numeric(x, errors="coerce").mean())
    neg = ok[ok["sentiment"] == "negative"].groupby(["week_id", "category"]).size().unstack(fill_value=0)
    for c in CATEGORIES:
        out[f"neg_{c}"] = neg[c] if c in neg else 0
    out = out.fillna(0).reset_index()
    out["week"] = "W" + out["week_id"].str.split("-W").str[1]
    return out
