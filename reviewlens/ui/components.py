"""Reusable Streamlit building blocks: styles, header, KPI row, urgent card, report view."""

import html
from collections.abc import Callable

import pandas as pd
import streamlit as st

from reviewlens.schemas import WeeklyInsights
from reviewlens.trends import Delta
from reviewlens.ui.charts import CATEGORY_LABELS

CSS = """
<style>
.block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1400px;}
[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {padding-bottom: 0;}
.rl-brand {display:flex; align-items:center; gap:.6rem; margin:.2rem 0 1.2rem 0;}
.rl-logo {width:34px; height:34px; border-radius:8px; background:linear-gradient(135deg,#3B82F6,#1D4ED8);
  display:flex; align-items:center; justify-content:center; color:#fff; font-weight:700; font-size:1rem;}
.rl-brand-name {font-weight:700; font-size:1.1rem; color:#F8FAFC; line-height:1.1;}
.rl-brand-sub {font-size:.75rem; color:#94A3B8;}
.rl-side-label {font-size:.7rem; letter-spacing:.08em; text-transform:uppercase; color:#94A3B8; margin:1rem 0 .3rem 0;}
.rl-header {display:flex; justify-content:space-between; align-items:flex-end; flex-wrap:wrap; gap:.5rem;
  border-bottom:1px solid #E2E8F0; padding-bottom:.9rem; margin-bottom:1.1rem;}
.rl-eyebrow {font-size:.75rem; letter-spacing:.08em; text-transform:uppercase; color:#1D4ED8; font-weight:600;}
.rl-title {font-size:1.65rem; font-weight:700; color:#0F172A; margin:.1rem 0 0 0;}
.rl-meta {font-size:.85rem; color:#64748B;}
.rl-step {background:#fff; border:1px solid #E2E8F0; border-radius:10px; padding:1.1rem 1.2rem; height:100%;}
.rl-step-num {font-size:.75rem; font-weight:700; color:#1D4ED8; letter-spacing:.06em;}
.rl-step-title {font-weight:600; font-size:1rem; margin:.25rem 0 .3rem 0; color:#0F172A;}
.rl-step-body {font-size:.88rem; color:#475569;}
.rl-review {font-size:.95rem; color:#0F172A; background:#F8FAFC; border-left:3px solid #CBD5E1;
  padding:.55rem .8rem; border-radius:4px; margin:.4rem 0;}
.rl-summary {font-size:.88rem; color:#334155;}
.rl-footer {font-size:.75rem; color:#94A3B8; margin-top:2.5rem; border-top:1px solid #E2E8F0; padding-top:.8rem;}
.rl-role-title {font-weight:700; font-size:1.05rem; color:#0F172A; margin-top:-.4rem;}
.rl-role-blurb {font-size:.85rem; color:#64748B; margin:.25rem 0 .7rem 0; min-height:2.6rem; line-height:1.3rem;}
.rl-cap-head {font-size:.68rem; letter-spacing:.08em; text-transform:uppercase; color:#94A3B8; font-weight:600;
  border-top:1px solid #E2E8F0; padding-top:.7rem; margin-bottom:.35rem;}
.rl-caps {list-style:none; padding:0 !important; margin:0 !important;}
.rl-cap {display:flex; gap:.55rem; align-items:flex-start; font-size:.86rem; line-height:1.25rem;
  padding:.18rem 0; margin:0 !important;}
.rl-cap.on {color:#0F172A;}
.rl-cap.off {color:#A3AEBD;}
.rl-cap-mark {width:1rem; flex:none; font-weight:700;}
.rl-cap.on .rl-cap-mark {color:#15803D;}
[data-testid="stMetric"] {background:#fff;}
.rl-theme {display:flex; gap:.75rem; padding:.6rem 0; border-bottom:1px solid #EEF2F7;}
.rl-theme:last-child {border-bottom:none;}
.rl-theme-num {flex:none; width:1.6rem; height:1.6rem; border-radius:50%; background:#FEE2E2; color:#B91C1C;
  font-weight:700; font-size:.8rem; display:flex; align-items:center; justify-content:center;}
.rl-theme-title {font-weight:600; color:#0F172A; font-size:.95rem;}
.rl-theme-count {margin-left:.5rem; font-size:.75rem; font-weight:600; color:#B91C1C; background:#FEF2F2;
  border-radius:999px; padding:.1rem .5rem;}
.rl-theme-note {font-size:.82rem; color:#64748B; margin-top:.15rem;}
</style>
"""

SENTIMENT_BADGE = {"positive": "green", "neutral": "gray", "negative": "red"}
URGENCY_BADGE = {"high": "red", "medium": "orange", "low": "gray"}


def inject_css() -> None:
    st.html(CSS)


def sidebar_brand() -> None:
    st.html(
        '<div class="rl-brand"><div class="rl-logo">RL</div><div>'
        '<div class="rl-brand-name">ReviewLens</div>'
        '<div class="rl-brand-sub">Customer Feedback Intelligence</div></div></div>'
    )


def side_label(text: str) -> None:
    st.html(f'<div class="rl-side-label">{html.escape(text)}</div>')


def page_header(title: str, meta: str, eyebrow: str = "Weekly feedback review") -> None:
    st.html(
        f'<div class="rl-header"><div><div class="rl-eyebrow">{html.escape(eyebrow)}</div>'
        f'<div class="rl-title">{html.escape(title)}</div></div>'
        f'<div class="rl-meta">{html.escape(meta)}</div></div>'
    )


def empty_state() -> None:
    steps = [
        (
            "01",
            "Upload the week's reviews",
            "CSV export from Google, Zomato, Swiggy or Amazon with columns "
            "review_id, date, platform, rating, review_text.",
        ),
        (
            "02",
            "Analyse with AI",
            "Every review is tagged with sentiment, category and urgency, summarised in "
            "English (incl. Tamil & Tanglish) and given a ready-to-post reply.",
        ),
        (
            "03",
            "Act on it",
            "Managers see the trends, support works the urgent queue, owners read a "
            "five-minute weekly report. Export everything to Excel.",
        ),
    ]
    cols = st.columns(3)
    for col, (num, title, body) in zip(cols, steps, strict=True):
        col.html(
            f'<div class="rl-step"><div class="rl-step-num">STEP {num}</div>'
            f'<div class="rl-step-title">{title}</div><div class="rl-step-body">{body}</div></div>'
        )


def _metric_delta(d: Delta | None) -> tuple[str | None, str]:
    if d is None or d.change is None:
        return None, "off"
    unit = " pts" if d.unit == "%" else d.unit
    value = f"{d.change:+.1f}{unit}" if d.unit == "★" else f"{d.change:+.0f}{unit}"
    color = "off" if d.higher_is_better is None else "normal" if d.higher_is_better else "inverse"
    return value, color


def kpi_row(stats: dict, deltas: dict[str, Delta] | None = None, prev_label: str = "") -> None:
    """Five headline metrics; arrows compare with the previous stored week."""
    p = stats["sentiment_pct"]
    d = deltas or {}
    vs = f" · vs {prev_label}" if prev_label and deltas else ""
    pos, neg = stats["sentiment_counts"]["positive"], stats["sentiment_counts"]["negative"]
    avg = stats.get("avg_rating")
    items = [
        ("Reviews", f"{stats['analysed']:,}", "reviews", f"Analysed reviews ({stats['total']} in file){vs}"),
        ("Positive", f"{p['positive']:.0f}%", "positive", f"{pos} reviews{vs}"),
        ("Negative", f"{p['negative']:.0f}%", "negative", f"{neg} reviews{vs}"),
        ("Urgent", f"{stats['urgent']}", "urgent", "HIGH urgency - reply today: health, refund, abuse, wrong order"),
        ("Average rating", f"{avg:.1f} ★" if avg is not None else "–", "avg_rating", f"out of 5{vs}"),
    ]
    for col, (label, value, key, help_text) in zip(st.columns(5), items, strict=True):
        delta, color = _metric_delta(d.get(key))
        col.metric(label, value, delta=delta, delta_color=color, help=help_text, border=True)


def urgent_card(
    row: dict,
    *,
    can_handle: bool,
    can_edit: bool,
    on_handled: Callable[[str, bool], None],
    on_save_reply: Callable[[str, str, str], None],
) -> None:
    """One urgent review: original text, English summary, copyable reply, handled + edit controls."""
    rid = str(row["review_id"])
    with st.container(border=True):
        rating = "" if pd.isna(row["rating"]) else "★" * int(row["rating"]) + "☆" * (5 - int(row["rating"]))
        key = f"handled_{rid}"
        # one row: details take the free space, the checkbox keeps its natural width (label never truncates)
        with st.container(horizontal=True, vertical_alignment="center", gap="small", wrap=False):
            st.markdown(
                f"**{html.escape(rid)}** &nbsp;·&nbsp; {html.escape(str(row['platform']))} "
                f"&nbsp;·&nbsp; {row['date']} &nbsp;·&nbsp; <span style='color:#D97706'>{rating}</span>",
                unsafe_allow_html=True,
                width="stretch",
            )
            st.checkbox(
                "Handled",
                value=bool(row.get("handled")),
                key=key,
                disabled=not can_handle,
                on_change=lambda: on_handled(rid, bool(st.session_state[key])),
                width="content",
            )
        with st.container(horizontal=True, gap="small"):
            st.badge(CATEGORY_LABELS.get(row["category"], row["category"]), color="blue")
            st.badge(row["language"], color="violet")
            st.badge(row["sentiment"].capitalize(), color=SENTIMENT_BADGE.get(row["sentiment"], "gray"))
            if row.get("edited"):
                st.badge("Edited", color="gray", icon=":material/edit:")
        st.html(f'<div class="rl-review">{html.escape(str(row["review_text"]))}</div>')
        st.html(f'<div class="rl-summary"><b>Summary:</b> {html.escape(str(row["summary"]))}</div>')
        lang = row["language"]
        st.caption(f"Suggested reply ({lang}) - review, then copy")
        st.code(row["suggested_reply"], language=None, wrap_lines=True)
        if lang != "English" and row.get("reply_english"):
            st.caption(f"English: {row['reply_english']}")
        if can_edit:
            with st.popover("Edit reply", icon=":material/edit:"):
                with st.form(f"reply_{rid}", border=False):
                    reply = st.text_area(f"Reply ({lang})", row["suggested_reply"], height=120)
                    reply_en = st.text_area("English version", row.get("reply_english") or "", height=100)
                    if st.form_submit_button("Save reply", type="primary"):
                        on_save_reply(rid, reply, reply_en)
                        st.rerun()


def report_view(
    stats: dict,
    insights: WeeklyInsights | None,
    date_range: str,
    deltas: dict[str, Delta] | None = None,
    movers: list[Delta] | None = None,
    prev_label: str = "",
) -> None:
    """Structured, readable version of the weekly report (with trend arrows when available)."""
    p = stats["sentiment_pct"]
    with st.container(border=True):
        st.markdown(f"#### Weekly feedback report &nbsp;·&nbsp; {date_range}")
        st.markdown(
            f"**{stats['total']} reviews** &nbsp;&nbsp; "
            f":green[Positive {p['positive']:.0f}%] &nbsp; :gray[Neutral {p['neutral']:.0f}%] &nbsp; "
            f":red[Negative {p['negative']:.0f}%] &nbsp;&nbsp; "
            f":red-badge[{stats['urgent']} urgent - reply within 24h]"
        )
        if deltas:
            parts = []
            for key in ("positive", "negative", "urgent", "avg_rating"):
                d = deltas[key]
                if d.change is None:
                    continue
                color = "gray" if d.good is None else "green" if d.good else "red"
                parts.append(f"{d.label} :{color}[{d.change_text()}]")
            mv = [m for m in (movers or []) if m.change][:3]
            if mv:
                parts.append(
                    "Complaints: "
                    + ", ".join(
                        f"{CATEGORY_LABELS.get(m.label, m.label)} :{'green' if m.good else 'red'}[{m.change_text()}]"
                        for m in mv
                    )
                )
            st.markdown(f"**vs {prev_label}** &nbsp; " + " &nbsp;·&nbsp; ".join(parts))
    if insights is None:
        st.warning("The AI report is not available for this week. A manager can regenerate it in Manage data.")
        return

    left, right = st.columns([3, 2], gap="medium")
    with left, st.container(border=True):
        st.markdown("##### Top complaints")
        if insights.top_complaints:
            st.html(
                "".join(
                    f'<div class="rl-theme"><div class="rl-theme-num">{i}</div><div class="rl-theme-body">'
                    f'<div class="rl-theme-title">{html.escape(t.theme)}'
                    f'<span class="rl-theme-count">{len(t.review_ids)} reviews</span></div>'
                    + (f'<div class="rl-theme-note">{html.escape(t.note)}</div>' if t.note else "")
                    + "</div></div>"
                    for i, t in enumerate(insights.top_complaints, 1)
                )
            )
        else:
            st.caption("No recurring complaints this week.")
        st.markdown("##### Top praise")
        if insights.top_praise:
            with st.container(horizontal=True, gap="small"):
                for t in insights.top_praise:
                    st.badge(f"{t.theme} · {len(t.review_ids)} mentions", color="green", icon=":material/thumb_up:")
        else:
            st.caption("No recurring praise this week.")
    with right, st.container(border=True):
        st.markdown("##### Action items")
        for i, a in enumerate(insights.action_items, 1):
            st.markdown(f"**{i}.** {a}")
        if stats["needs_review"]:
            st.warning(f"{stats['needs_review']} review(s) could not be analysed and need manual review.")


def footer(model: str) -> None:
    st.html(
        f'<div class="rl-footer">ReviewLens · model {html.escape(model)} · Counts and percentages are calculated '
        "from your data; summaries and replies are AI-generated - review before posting.</div>"
    )


def role_card_body(title: str, blurb: str, caps: list[tuple[str, bool]]) -> str:
    """Role picker card: title, blurb and the full capability list (same rows on every card)."""
    rows = "".join(
        f'<li class="rl-cap {"on" if ok else "off"}"><span class="rl-cap-mark">{"✓" if ok else "–"}</span>'
        f"<span>{html.escape(label)}</span></li>"
        for label, ok in caps
    )
    return (
        f'<div class="rl-role-title">{html.escape(title)}</div>'
        f'<div class="rl-role-blurb">{html.escape(blurb)}</div>'
        f'<div class="rl-cap-head">What you can do</div><ul class="rl-caps">{rows}</ul>'
    )
