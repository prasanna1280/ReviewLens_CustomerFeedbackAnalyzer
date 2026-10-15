import pandas as pd
from langchain_core.runnables import RunnableLambda

from reviewlens.chains.report import generate_insights, sanitize_insights
from reviewlens.data.aggregate import compute_stats
from reviewlens.data.export import to_excel_csv
from reviewlens.data.loader import STATUS_OK, enrich, load_reviews
from reviewlens.report_render import render_report
from reviewlens.schemas import Theme, WeeklyInsights
from tests.conftest import SAMPLE_FULL, make_analysis


def enriched_frame() -> pd.DataFrame:
    df = load_reviews(str(SAMPLE_FULL)).df
    results = []
    for i, r in enumerate(df.to_dict("records")):
        if i % 17 == 0:
            results.append(ValueError("bad"))
        elif r["rating"] is not pd.NA and r["rating"] >= 4:
            results.append(make_analysis(sentiment="positive", category="food_quality", urgency="low"))
        elif r["rating"] is not pd.NA and r["rating"] == 3:
            results.append(make_analysis(sentiment="neutral", category="price", urgency="medium", language="Tanglish"))
        else:
            results.append(make_analysis())
    return enrich(df, results)


def test_stats_match_pandas_value_counts():
    df = enriched_frame()
    stats = compute_stats(df)
    ok = df[df["status"] == STATUS_OK]
    assert stats["total"] == len(df)
    assert stats["analysed"] == len(ok)
    assert stats["needs_review"] == (df["status"] != STATUS_OK).sum()
    for col in ("sentiment", "category", "urgency", "language"):
        vc = ok[col].value_counts()
        for k, v in stats[f"{col}_counts"].items():
            assert v == vc.get(k, 0)
    assert stats["urgent"] == (ok["urgency"] == "high").sum()
    assert abs(sum(stats["sentiment_pct"].values()) - 100) < 1e-9
    assert stats["category_counts"]["app"] == 0  # zero-filled


def test_sanitize_drops_invented_and_duplicate_ids():
    raw = WeeklyInsights(
        top_complaints=[
            Theme(theme="Late delivery", review_ids=["R-1", "R-2", "R-2", "R-999"], note="mostly Swiggy"),
            Theme(theme="Ghost", review_ids=["R-404"], note=""),
        ],
        top_praise=[Theme(theme="Biryani taste", review_ids=["R-3"], note="")],
        action_items=["a", "b", "c", "d"],
    )
    clean = sanitize_insights(raw, {"R-1", "R-2", "R-3"})
    assert [t.theme for t in clean.top_complaints] == ["Late delivery"]
    assert clean.top_complaints[0].review_ids == ["R-1", "R-2"]
    assert len(clean.action_items) == 3


def test_report_numbers_come_from_stats():
    df = enriched_frame()
    stats = compute_stats(df)
    ok_ids = list(df.loc[df["status"] == STATUS_OK, "review_id"])
    fake = RunnableLambda(
        lambda _: WeeklyInsights(
            top_complaints=[Theme(theme="Late delivery", review_ids=ok_ids[:7] + ["R-FAKE"], note="mostly Swiggy")],
            top_praise=[Theme(theme="Biryani taste", review_ids=ok_ids[7:12], note="")],
            action_items=["Add a rider", "Show charges", "Reply to urgent reviews"],
        )
    )
    insights = generate_insights(fake, df[df["status"] == STATUS_OK], stats)
    text = render_report(stats, insights)
    p = stats["sentiment_pct"]
    assert f"Total reviews: {stats['total']}" in text
    assert f"Positive {p['positive']:.0f}%" in text
    assert "7 reviews" in text  # R-FAKE dropped before counting
    assert "Biryani taste (5 mentions)" in text
    assert f"URGENT: {stats['urgent']} reviews" in text
    assert "28 Sep to 4 Oct 2026" in text
    assert "need manual review" in text
    assert text.count("\n  ") >= 5


def test_export_is_excel_safe_and_round_trips():
    df = enriched_frame()
    data = to_excel_csv(df)
    assert data.startswith(b"\xef\xbb\xbf")
    back = pd.read_csv(pd.io.common.BytesIO(data), encoding="utf-8-sig", dtype=str, keep_default_na=False)
    assert list(back.columns) == list(df.columns)
    assert len(back) == len(df)
    assert back["review_text"].str.contains("பிரியாணி").any()
