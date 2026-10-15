"""Altair charts with one consistent palette. Inputs are pandas results, never LLM numbers."""

import altair as alt
import pandas as pd

from reviewlens.schemas import CATEGORIES, SENTIMENTS, URGENCIES

SENTIMENT_COLORS = {"positive": "#15803D", "neutral": "#94A3B8", "negative": "#B91C1C"}
URGENCY_COLORS = {"high": "#B91C1C", "medium": "#D97706", "low": "#64748B"}
FONT = "Inter, sans-serif"

CATEGORY_LABELS = {
    "food_quality": "Food quality",
    "delivery": "Delivery",
    "price": "Price",
    "staff": "Staff",
    "packaging": "Packaging",
    "app": "App",
}


def _scale(colors: dict[str, str]) -> alt.Scale:
    return alt.Scale(domain=list(colors), range=list(colors.values()))


def _style(chart: alt.Chart, height: int) -> alt.Chart:
    return (
        chart.properties(height=height)
        .configure(font=FONT, background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor="#475569", titleColor="#475569", gridColor="#E2E8F0", domain=False, ticks=False, labelFontSize=12
        )
        .configure_legend(
            orient="bottom",
            title=None,
            labelColor="#334155",
            labelFontSize=12,
            symbolType="circle",
            direction="horizontal",
        )
    )


def sentiment_donut(counts: dict[str, int]) -> alt.Chart:
    data = pd.DataFrame({"sentiment": list(counts), "reviews": list(counts.values())})
    data["share"] = data["reviews"] / max(data["reviews"].sum(), 1)
    chart = (
        alt.Chart(data)
        .mark_arc(innerRadius=62, outerRadius=100, cornerRadius=3, padAngle=0.015)
        .encode(
            theta=alt.Theta("reviews:Q", stack=True),
            color=alt.Color("sentiment:N", scale=_scale(SENTIMENT_COLORS), sort=list(SENTIMENTS)),
            order=alt.Order("sentiment_order:Q"),
            tooltip=[
                alt.Tooltip("sentiment:N", title="Sentiment"),
                alt.Tooltip("reviews:Q", title="Reviews"),
                alt.Tooltip("share:Q", title="Share", format=".0%"),
            ],
        )
        .transform_calculate(sentiment_order="indexof(['positive','neutral','negative'], datum.sentiment)")
    )
    return _style(chart, 260)


def category_by_sentiment(df_ok: pd.DataFrame) -> alt.Chart:
    data = df_ok.groupby(["category", "sentiment"]).size().reset_index(name="reviews")
    data["category_label"] = data["category"].map(CATEGORY_LABELS)
    order = data.groupby("category_label")["reviews"].sum().reindex([CATEGORY_LABELS[c] for c in CATEGORIES]).fillna(0)
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=3, height=18)
        .encode(
            y=alt.Y("category_label:N", sort=list(order.sort_values(ascending=False).index), title=None),
            x=alt.X("reviews:Q", title="Reviews"),
            color=alt.Color("sentiment:N", scale=_scale(SENTIMENT_COLORS), sort=list(SENTIMENTS)),
            order=alt.Order("sentiment_order:Q"),
            tooltip=[
                alt.Tooltip("category_label:N", title="Category"),
                alt.Tooltip("sentiment:N", title="Sentiment"),
                alt.Tooltip("reviews:Q", title="Reviews"),
            ],
        )
        .transform_calculate(sentiment_order="indexof(['positive','neutral','negative'], datum.sentiment)")
    )
    return _style(chart, 260)


def platform_by_sentiment(df_ok: pd.DataFrame) -> alt.Chart:
    data = df_ok.groupby(["platform", "sentiment"]).size().reset_index(name="reviews")
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, width={"band": 0.6})
        .encode(
            x=alt.X("platform:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("reviews:Q", title="Reviews"),
            color=alt.Color("sentiment:N", scale=_scale(SENTIMENT_COLORS), sort=list(SENTIMENTS)),
            order=alt.Order("sentiment_order:Q"),
            tooltip=["platform", "sentiment", "reviews"],
        )
        .transform_calculate(sentiment_order="indexof(['positive','neutral','negative'], datum.sentiment)")
    )
    return _style(chart, 260)


def daily_trend(df_ok: pd.DataFrame) -> alt.Chart:
    data = df_ok.assign(day=pd.to_datetime(df_ok["date"], errors="coerce")).dropna(subset=["day"])
    data = data.groupby(["day", "sentiment"]).size().reset_index(name="reviews")
    chart = (
        alt.Chart(data)
        .mark_line(point=alt.OverlayMarkDef(size=40), strokeWidth=2.5)
        .encode(
            x=alt.X("day:T", title=None, axis=alt.Axis(format="%a %d %b", labelAngle=0)),
            y=alt.Y("reviews:Q", title="Reviews"),
            color=alt.Color("sentiment:N", scale=_scale(SENTIMENT_COLORS), sort=list(SENTIMENTS)),
            tooltip=[alt.Tooltip("day:T", title="Date", format="%a %d %b"), "sentiment", "reviews"],
        )
    )
    return _style(chart, 260)


def urgency_bars(counts: dict[str, int]) -> alt.Chart:
    data = pd.DataFrame({"urgency": list(counts), "reviews": list(counts.values())})
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusEnd=3, height=18)
        .encode(
            y=alt.Y("urgency:N", sort=list(reversed(URGENCIES)), title=None),
            x=alt.X("reviews:Q", title="Reviews"),
            color=alt.Color("urgency:N", scale=_scale(URGENCY_COLORS), legend=None),
            tooltip=["urgency", "reviews"],
        )
    )
    return _style(chart, 140)


# ---------------------------------------------------------------- multi-week trends
def weekly_sentiment(series: pd.DataFrame, current_week: str | None = None) -> alt.Chart:
    data = series.melt(
        id_vars=["week", "week_id"],
        value_vars=[f"{s}_pct" for s in SENTIMENTS],
        var_name="sentiment",
        value_name="share",
    )
    data["sentiment"] = data["sentiment"].str.replace("_pct", "")
    base = alt.Chart(data).encode(
        x=alt.X("week:N", title=None, sort=list(series["week"]), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("share:Q", title="% of reviews", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("sentiment:N", scale=_scale(SENTIMENT_COLORS), sort=list(SENTIMENTS)),
        tooltip=["week", "sentiment", alt.Tooltip("share:Q", format=".0f", title="%")],
    )
    layers = [base.mark_line(strokeWidth=2.5), base.mark_point(size=60, filled=True)]
    if current_week:
        rule = alt.Chart(pd.DataFrame({"week": [current_week]})).mark_rule(color="#CBD5E1", strokeDash=[4, 4])
        layers.insert(0, rule.encode(x=alt.X("week:N", sort=list(series["week"]))))
    return _style(alt.layer(*layers), 260)


def weekly_urgent(series: pd.DataFrame) -> alt.Chart:
    chart = (
        alt.Chart(series)
        .mark_bar(color=URGENCY_COLORS["high"], cornerRadiusTopLeft=3, cornerRadiusTopRight=3, width={"band": 0.5})
        .encode(
            x=alt.X("week:N", title=None, sort=list(series["week"]), axis=alt.Axis(labelAngle=0)),
            y=alt.Y("urgent:Q", title="Urgent reviews"),
            tooltip=["week", "urgent", alt.Tooltip("avg_rating:Q", format=".2f", title="Avg rating")],
        )
    )
    return _style(chart, 260)


def complaints_heatmap(series: pd.DataFrame) -> alt.Chart:
    data = series.melt(id_vars=["week"], value_vars=[f"neg_{c}" for c in CATEGORIES], var_name="cat", value_name="n")
    data["category"] = data["cat"].str.replace("neg_", "").map(CATEGORY_LABELS)
    base = alt.Chart(data).encode(
        x=alt.X("week:N", title=None, sort=list(series["week"]), axis=alt.Axis(labelAngle=0, orient="top")),
        y=alt.Y("category:N", title=None, sort=[CATEGORY_LABELS[c] for c in CATEGORIES]),
    )
    heat = base.mark_rect(cornerRadius=3).encode(
        color=alt.Color("n:Q", scale=alt.Scale(scheme="reds"), legend=None),
        tooltip=["week", "category", alt.Tooltip("n:Q", title="Negative reviews")],
    )
    text = base.mark_text(fontSize=12, fontWeight=600).encode(
        text="n:Q", color=alt.condition("datum.n > 20", alt.value("white"), alt.value("#0F172A"))
    )
    return _style(heat + text, 230)
