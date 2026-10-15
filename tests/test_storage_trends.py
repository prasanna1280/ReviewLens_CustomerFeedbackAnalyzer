import pandas as pd
import pytest

from reviewlens.data.aggregate import compute_stats
from reviewlens.data.loader import enrich, load_reviews
from reviewlens.pipeline import import_history
from reviewlens.report_render import render_report
from reviewlens.schemas import Theme, WeeklyInsights
from reviewlens.storage import Store, week_id_for, week_label
from reviewlens.trends import category_complaint_deltas, compare, trend_text, weekly_series
from tests.conftest import SAMPLE_FULL, make_analysis

INSIGHTS = WeeklyInsights(
    top_complaints=[Theme(theme="Late delivery", review_ids=["R-1101"], note="")],
    top_praise=[],
    action_items=["a", "b", "c"],
)


def week_frame(neg_every: int) -> pd.DataFrame:
    df = load_reviews(str(SAMPLE_FULL)).df
    results = [
        make_analysis() if i % neg_every == 0 else make_analysis(sentiment="positive", urgency="low")
        for i in range(len(df))
    ]
    return enrich(df, results)


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_week_id_and_label():
    assert week_id_for(pd.Series(["2026-09-28", "2026-10-01", "2026-10-04"])) == "2026-W40"
    assert week_label("2026-W40", "2026-09-28", "2026-10-04") == "Week 40 · 28 Sep – 4 Oct 2026"


def test_save_and_reload_round_trip(store):
    df = week_frame(3)
    store.save_week("2026-W40", df, INSIGHTS, "report", "file.csv", "openai:x")
    back = store.get_reviews("2026-W40")
    assert len(back) == len(df)
    assert compute_stats(back) == compute_stats(df)
    meta = store.get_week("2026-W40")
    assert meta["insights"] == INSIGHTS and meta["label"].startswith("Week 40")
    assert store.latest_week_id() == "2026-W40"


def test_replace_week_and_previous(store):
    store.save_week("2026-W39", week_frame(2), None, "", "", "")
    store.save_week("2026-W40", week_frame(3), None, "", "", "")
    store.save_week("2026-W40", week_frame(4), None, "", "", "")  # replace
    assert list(store.list_weeks()["week_id"]) == ["2026-W40", "2026-W39"]
    assert store.previous_week_id("2026-W40") == "2026-W39"
    assert store.previous_week_id("2026-W39") is None
    store.delete_week("2026-W39")
    assert store.get_reviews("2026-W39").empty  # cascade


def test_update_review_respects_whitelist(store):
    store.save_week("2026-W40", week_frame(3), None, "", "", "")
    rid = store.get_reviews("2026-W40")["review_id"].iloc[0]
    store.update_review("2026-W40", rid, {"category": "staff", "review_text": "HACK"}, allowed={"suggested_reply"})
    row = store.get_reviews("2026-W40").set_index("review_id").loc[rid]
    assert row["category"] != "staff" and row["review_text"] != "HACK"

    store.update_review("2026-W40", rid, {"category": "staff", "handled": True})
    row = store.get_reviews("2026-W40").set_index("review_id").loc[rid]
    assert row["category"] == "staff" and row["handled"] and row["edited"]


def test_settings_and_email_log(store):
    store.set_setting("k", "v")
    assert store.get_setting("k") == "v" and store.get_setting("missing", "d") == "d"
    store.save_week("2026-W40", week_frame(3), None, "", "", "")
    store.log_email("2026-W40", ["a@x.com"], "weekly", "sent")
    assert store.list_weeks()["emailed_at"].notna().all()


def test_trend_deltas_and_text():
    prev, cur = compute_stats(week_frame(2)), compute_stats(week_frame(4))
    d = compare(cur, prev)
    assert d["negative"].change < 0 and d["negative"].good is True and d["negative"].arrow == "▼"
    assert d["positive"].good is True and d["urgent"].good is True
    assert d["reviews"].good is None
    movers = category_complaint_deltas(cur, prev)
    assert movers[0].label == "delivery" and movers[0].change < 0
    text = trend_text(cur, prev, "Week 39")
    assert "Compared with Week 39" in text and "▼" in text
    report = render_report(cur, INSIGHTS, prev, "Week 39")
    assert "VS WEEK 39" in report and "Negative ▼" in report


def test_weekly_series(store):
    store.save_week("2026-W39", week_frame(2), None, "", "", "")
    store.save_week("2026-W40", week_frame(4), None, "", "", "")
    s = weekly_series(store.all_reviews())
    assert list(s["week"]) == ["W39", "W40"]
    assert s["negative_pct"].iloc[0] > s["negative_pct"].iloc[1]
    assert (s[["positive_pct", "neutral_pct", "negative_pct"]].sum(axis=1).round(6) == 100).all()


def test_demo_history_imports(store):
    weeks = import_history(store)
    assert weeks == ["2026-W38", "2026-W39", "2026-W40"]
    for w in weeks:
        df = store.get_reviews(w)
        assert len(df) >= 200 and (df["status"] == "ok").all()
        assert store.get_week(w)["insights"] is not None
