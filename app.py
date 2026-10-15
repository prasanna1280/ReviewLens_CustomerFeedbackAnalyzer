"""ReviewLens - Streamlit UI. Wiring and presentation only; logic lives in the reviewlens package."""

import hmac
import logging
import os
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from reviewlens.chains.classify import build_classify_chain, classify_reviews
from reviewlens.chains.report import build_report_chain, generate_insights
from reviewlens.config import settings
from reviewlens.data.aggregate import compute_stats
from reviewlens.data.export import to_excel_csv
from reviewlens.data.loader import (
    STATUS_OK,
    InvalidCSVError,
    LoadResult,
    enrich,
    load_reviews,
    to_chain_inputs,
)
from reviewlens.llm import LLMConfigError, get_llm
from reviewlens.report_render import render_report
from reviewlens.schemas import SENTIMENTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("reviewlens.app")

SAMPLE = Path(__file__).parent / "data" / "sample" / "reviews_week40_full.csv"
MAX_ROWS = int(os.getenv("MAX_ROWS", "1000"))
SENTIMENT_COLORS = {"positive": "#2e9e5b", "neutral": "#9aa0a6", "negative": "#d64545"}

st.set_page_config(page_title="ReviewLens", page_icon="🔎", layout="wide")


def require_password() -> None:
    """Simple shared-password gate, enabled when APP_PASSWORD is set."""
    expected = os.getenv("APP_PASSWORD", "")
    if not expected or st.session_state.get("authed"):
        return
    st.title("🔎 ReviewLens")
    pw = st.text_input("Password", type="password")
    if pw and hmac.compare_digest(pw, expected):
        st.session_state.authed = True
        st.rerun()
    elif pw:
        st.error("Wrong password.")
    st.stop()


def bar_chart(count_map: dict[str, int], title: str, colors: dict[str, str] | None = None) -> alt.Chart:
    data = pd.DataFrame({"label": list(count_map), "count": list(count_map.values())})
    color = (
        alt.Color("label:N", scale=alt.Scale(domain=list(colors), range=list(colors.values())), legend=None)
        if colors
        else alt.value("#4c78a8")
    )
    return (
        alt.Chart(data, title=title)
        .mark_bar()
        .encode(
            x=alt.X("label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("count:Q", title="Reviews"),
            color=color,
            tooltip=["label", "count"],
        )
    )


def reset_results() -> None:
    for key in ("enriched", "stats", "report_text"):
        st.session_state.pop(key, None)


def run_analysis(loaded: LoadResult) -> None:
    """Classify, aggregate and report; store results in session state."""
    try:
        llm = get_llm()
    except LLMConfigError as exc:
        log.exception("model init failed")
        st.error(f"{exc}\n\nCheck LLM_MODEL and OPENAI_API_KEY in your .env (see .env.example).")
        st.stop()

    df = loaded.df
    bar = st.progress(0.0, text=f"Classifying {len(df)} reviews…")

    def on_progress(done: int, total: int) -> None:
        bar.progress(done / total, text=f"Classified {done}/{total} reviews")

    results = classify_reviews(
        build_classify_chain(llm),
        to_chain_inputs(df),
        max_concurrency=settings.max_concurrency,
        max_retries=settings.max_retries,
        on_progress=on_progress,
        chunk_size=settings.chunk_size,
    )
    enriched = enrich(df, results)
    stats = compute_stats(enriched)

    bar.progress(1.0, text="Writing weekly report…")
    try:
        insights = generate_insights(build_report_chain(llm), enriched[enriched["status"] == STATUS_OK], stats)
        report_text = render_report(stats, insights)
    except Exception:
        log.exception("report chain failed")
        report_text = "The weekly report could not be generated. Please try again."
    bar.empty()

    st.session_state.enriched = enriched
    st.session_state.stats = stats
    st.session_state.report_text = report_text


def render_results() -> None:
    df: pd.DataFrame = st.session_state.enriched
    stats: dict = st.session_state.stats
    p = stats["sentiment_pct"]

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total reviews", stats["total"])
    k2.metric("Positive", f"{p['positive']:.0f}%")
    k3.metric("Negative", f"{p['negative']:.0f}%")
    k4.metric("Urgent (HIGH)", stats["urgent"])
    k5.metric("Needs review", stats["needs_review"])
    if stats["needs_review"]:
        st.warning(
            f"{stats['needs_review']} review(s) could not be analysed after retries. They are marked "
            "'needs_review' in the table."
        )

    tab_dash, tab_report, tab_table = st.tabs(["📊 Dashboard", "📝 Weekly report", "📋 Reviews"])

    with tab_dash:
        c1, c2 = st.columns(2)
        sentiment = {k: stats["sentiment_counts"][k] for k in SENTIMENTS}
        c1.altair_chart(bar_chart(sentiment, "Sentiment split", SENTIMENT_COLORS), width="stretch")
        c2.altair_chart(bar_chart(stats["category_counts"], "Reviews by category"), width="stretch")
        c3, c4 = st.columns(2)
        c3.altair_chart(bar_chart(stats["urgency_counts"], "Urgency"), width="stretch")
        c4.altair_chart(bar_chart(stats["platform_counts"], "Platform"), width="stretch")

    with tab_report:
        st.code(st.session_state.report_text, language=None)
        st.download_button(
            "Download report (.txt)",
            st.session_state.report_text.encode("utf-8"),
            file_name=f"reviewlens_report_{date.today()}.txt",
            mime="text/plain",
        )

    with tab_table:
        f1, f2, f3 = st.columns([1, 2, 2])
        high_only = f1.toggle("HIGH urgency only")
        platforms = f2.multiselect("Platform", sorted(df["platform"].unique()))
        categories = f3.multiselect("Category", sorted(c for c in df["category"].unique() if c))
        view = df
        if high_only:
            view = view[view["urgency"] == "high"]
        if platforms:
            view = view[view["platform"].isin(platforms)]
        if categories:
            view = view[view["category"].isin(categories)]
        st.caption(f"Showing {len(view)} of {len(df)} reviews")
        st.dataframe(view, width="stretch", hide_index=True)
        st.download_button(
            "Download enriched CSV (all reviews)",
            to_excel_csv(df),
            file_name=f"reviewlens_enriched_{date.today()}.csv",
            mime="text/csv",
            type="primary",
        )


def main() -> None:
    require_password()
    st.title("🔎 ReviewLens")
    st.caption("Turn this week's customer reviews into tagged, prioritised insights and a weekly report.")

    with st.sidebar:
        st.subheader("Settings")
        st.text(f"Model: {settings.llm_model}")
        st.text(f"Concurrency: {settings.max_concurrency}  ·  Retries: {settings.max_retries}")
        st.caption("CSV columns: review_id, date, platform, rating, review_text")

    uploaded = st.file_uploader("Upload this week's reviews (CSV)", type="csv")
    use_sample = st.checkbox("Use sample data (233 rows, week 40)", disabled=uploaded is not None)

    source, source_key = None, None
    if uploaded is not None:
        source, source_key = uploaded.getvalue(), f"upload:{uploaded.name}:{uploaded.size}"
    elif use_sample:
        source, source_key = str(SAMPLE), "sample"
    if source_key != st.session_state.get("source_key"):
        reset_results()
        st.session_state.source_key = source_key
    if source is None:
        st.info("Upload a CSV or tick 'Use sample data' to begin.")
        return

    try:
        loaded = load_reviews(source)
    except InvalidCSVError as exc:
        st.error(str(exc))
        return

    msg = f"✅ {len(loaded.df)} reviews ready"
    if loaded.dropped:
        msg += f" · {len(loaded.dropped)} row(s) dropped"
    st.write(msg)
    if loaded.dropped:
        with st.expander("Dropped rows"):
            st.dataframe(pd.DataFrame(loaded.dropped), hide_index=True)
    for w in loaded.warnings:
        st.caption(f"⚠️ {w}")

    if len(loaded.df) > MAX_ROWS:
        st.error(f"This file has {len(loaded.df)} reviews; the limit is {MAX_ROWS} per run.")
        return

    if st.button("Analyse reviews", type="primary"):
        run_analysis(loaded)
    if "enriched" in st.session_state:
        render_results()


main()
