import pytest
from pydantic import ValidationError

from reviewlens.chains.classify import classify_reviews
from reviewlens.data.loader import STATUS_NEEDS_REVIEW, STATUS_OK, enrich, load_reviews, to_chain_inputs
from reviewlens.schemas import ANALYSIS_FIELDS, CATEGORIES, SENTIMENTS, URGENCIES, ReviewAnalysis
from tests.conftest import SAMPLE_FULL, make_analysis


def rows(n: int) -> list[dict]:
    return [{"platform": "Swiggy", "rating": 1, "review_text": f"late order {i}"} for i in range(n)]


def test_happy_path(fake_chain):
    out = classify_reviews(fake_chain, rows(5), max_concurrency=2, max_retries=1)
    assert all(isinstance(r, ReviewAnalysis) for r in out)


def test_invalid_output_is_retried_then_succeeds(flaky_chain):
    out = classify_reviews(flaky_chain, rows(10), max_concurrency=3, max_retries=2)
    assert all(isinstance(r, ReviewAnalysis) for r in out)


def test_persistent_failure_marks_needs_review(broken_chain):
    loaded = load_reviews(str(SAMPLE_FULL)).df.head(7)
    out = classify_reviews(broken_chain, to_chain_inputs(loaded), max_concurrency=3, max_retries=2)
    assert all(isinstance(r, Exception) for r in out)
    df = enrich(loaded, out)
    assert (df["status"] == STATUS_NEEDS_REVIEW).all()
    assert df["error"].str.contains("invalid output").all()


def test_250_rows_complete_in_order_with_progress(fake_chain):
    data = rows(250)
    progress = []
    out = classify_reviews(fake_chain, data, 5, 2, on_progress=lambda d, t: progress.append((d, t)), chunk_size=25)
    assert len(out) == 250
    assert progress[-1] == (250, 250) and len(progress) == 10


def test_full_sample_every_row_has_all_six_fields(fake_chain):
    loaded = load_reviews(str(SAMPLE_FULL)).df
    df = enrich(loaded, classify_reviews(fake_chain, to_chain_inputs(loaded), 5, 1))
    assert (df["status"] == STATUS_OK).all()
    for f in ANALYSIS_FIELDS:
        assert df[f].astype(str).str.len().gt(0).all(), f
    assert df["sentiment"].isin(SENTIMENTS).all()
    assert df["category"].isin(CATEGORIES).all()
    assert df["urgency"].isin(URGENCIES).all()


@pytest.mark.parametrize(
    "field,value", [("category", "service"), ("sentiment", "angry"), ("urgency", "urgent"), ("language", "Hindi")]
)
def test_schema_rejects_values_outside_allowed_lists(field, value):
    with pytest.raises(ValidationError):
        make_analysis(**{field: value})
