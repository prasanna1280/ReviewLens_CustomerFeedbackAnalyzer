from pathlib import Path

import pytest
from langchain_core.runnables import RunnableLambda

from reviewlens.schemas import ReviewAnalysis

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_SMALL = ROOT / "data" / "sample" / "reviews_week40.csv"
SAMPLE_FULL = ROOT / "data" / "sample" / "reviews_week40_full.csv"


def make_analysis(**over) -> ReviewAnalysis:
    base = dict(
        sentiment="negative",
        category="delivery",
        urgency="high",
        language="English",
        summary="Order arrived late and cold.",
        suggested_reply="We are sorry about the delay.",
    )
    return ReviewAnalysis(**{**base, **over})


@pytest.fixture
def fake_chain():
    """Deterministic fake: rating >= 4 positive/low, else negative/high."""

    def run(row: dict) -> ReviewAnalysis:
        rating = row["rating"] if isinstance(row["rating"], int) else 3
        if rating >= 4:
            return make_analysis(sentiment="positive", category="food_quality", urgency="low")
        return make_analysis()

    return RunnableLambda(run)


@pytest.fixture
def flaky_chain():
    """Fails the first call per review_text (like an invalid category), then succeeds."""
    seen: set[str] = set()

    def run(row: dict) -> ReviewAnalysis:
        if row["review_text"] not in seen:
            seen.add(row["review_text"])
            raise ValueError("category 'service' is not in the allowed list")
        return make_analysis()

    return RunnableLambda(run)


@pytest.fixture
def broken_chain():
    def run(row: dict) -> ReviewAnalysis:
        raise ValueError("invalid output")

    return RunnableLambda(run)
