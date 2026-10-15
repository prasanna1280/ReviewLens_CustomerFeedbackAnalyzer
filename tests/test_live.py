"""Real-LLM smoke tests. Run with: pytest -m live (needs OPENAI_API_KEY in .env)."""

import pytest

from reviewlens.chains.classify import build_classify_chain, classify_reviews
from reviewlens.chains.report import build_report_chain, generate_insights
from reviewlens.config import settings
from reviewlens.data.aggregate import compute_stats
from reviewlens.data.loader import STATUS_OK, enrich, load_reviews, to_chain_inputs
from reviewlens.llm import get_llm
from reviewlens.report_render import render_report
from tests.conftest import SAMPLE_SMALL

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def enriched():
    llm = get_llm()
    df = load_reviews(str(SAMPLE_SMALL)).df
    results = classify_reviews(build_classify_chain(llm), to_chain_inputs(df), settings.max_concurrency, 2)
    return llm, enrich(df, results).set_index("review_id", drop=False)


def test_all_rows_analysed(enriched):
    _, df = enriched
    assert (df["status"] == STATUS_OK).all(), df["error"].tolist()


def test_brief_sample_output(enriched):
    _, df = enriched
    r = df.loc["R-1042"]
    assert (r.sentiment, r.category, r.urgency) == ("negative", "delivery", "high")
    assert df.loc["R-1041", "sentiment"] == "positive"


def test_tanglish_gets_english_summary(enriched):
    _, df = enriched
    r = df.loc["R-1043"]
    assert r.language == "Tanglish"
    assert r.summary.isascii() and "bill" in r.summary.lower() or "charge" in r.summary.lower()


def test_report_chain(enriched):
    llm, df = enriched
    stats = compute_stats(df)
    insights = generate_insights(build_report_chain(llm), df[df["status"] == STATUS_OK], stats)
    assert len(insights.action_items) == 3
    text = render_report(stats, insights)
    assert "Total reviews: 3" in text
