"""ReviewLens - Streamlit UI. Wiring and presentation only; logic lives in the reviewlens package."""

import logging
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from reviewlens import roles as R
from reviewlens.config import settings
from reviewlens.data.aggregate import compute_stats
from reviewlens.data.export import to_excel_csv
from reviewlens.data.loader import REQUIRED_COLUMNS, STATUS_OK, InvalidCSVError, load_reviews
from reviewlens.emailer import (
    RECIPIENTS_KEY,
    SMTPConfig,
    parse_recipients,
    preview_html,
    recipients,
    send_weekly_report,
)
from reviewlens.llm import LLMConfigError, get_llm
from reviewlens.pipeline import analyse_and_save, classify_one, ensure_demo_history, regenerate_report
from reviewlens.report_render import date_range_label, render_report
from reviewlens.scheduler import DAY_KEY, DAYS, ENABLED_KEY, TIME_KEY, schedule_config
from reviewlens.schemas import CATEGORIES, LANGUAGES, SENTIMENTS, URGENCIES
from reviewlens.storage import EDITABLE_FIELDS, SUPPORT_FIELDS, Store, week_id_for, week_label
from reviewlens.trends import category_complaint_deltas, compare, weekly_series
from reviewlens.ui import charts
from reviewlens.ui import components as ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("reviewlens.app")

SAMPLE_DIR = Path(__file__).parent / "data" / "sample"
SAMPLE_WEEKS = {
    "Week 41 · 5–11 Oct (new, not yet analysed)": "reviews_week41.csv",
    "Week 40 · 28 Sep–4 Oct": "reviews_week40_full.csv",
    "Week 39 · 21–27 Sep": "reviews_week39.csv",
    "Week 38 · 14–20 Sep": "reviews_week38.csv",
}
MAX_ROWS = int(os.getenv("MAX_ROWS", "1000"))

st.set_page_config(
    page_title="ReviewLens · Customer Feedback Intelligence",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)
ui.inject_css()


@st.cache_resource
def get_store() -> Store:
    store = Store()
    ensure_demo_history(store)
    return store


@st.cache_resource
def cached_llm():
    return get_llm()


def llm_or_stop():
    try:
        return cached_llm()
    except LLMConfigError as exc:
        st.error(f"{exc}\n\nCheck LLM_MODEL and OPENAI_API_KEY in .env.", icon=":material/error:")
        st.stop()


# ====================================================================== role gate
def role_gate() -> R.Role:
    role_key = st.session_state.get("role")
    if role_key in R.ROLES:
        return R.ROLES[role_key]

    st.html("<style>.block-container{padding-top:2.2rem}</style>")
    st.html(
        '<div style="text-align:center"><div class="rl-brand" style="justify-content:center">'
        '<div class="rl-logo">RL</div><div style="text-align:left">'
        '<div class="rl-title" style="font-size:1.5rem;margin:0">ReviewLens</div>'
        '<div class="rl-meta">Customer Feedback Intelligence</div></div></div>'
        '<div class="rl-meta" style="margin-top:.4rem">Choose your workspace</div></div>'
    )
    _, mid, _ = st.columns([0.4, 5, 0.4])
    with mid:
        cols = st.columns(3, gap="medium")
        for col, role in zip(cols, R.ROLES.values(), strict=True):
            with col, st.container(border=True):
                st.markdown(f"#### {role.icon}")
                st.html(ui.role_card_body(role.title, role.blurb, R.capabilities(role.key)))
                if st.button(
                    f"Continue as {role.title.split()[-1]}",
                    key=f"pick_{role.key}",
                    type="primary",
                    width="stretch",
                ):
                    if R.pin_for(role.key):
                        st.session_state.pending_role = role.key
                    else:
                        st.session_state.role = role.key
                    st.rerun()

        pending = st.session_state.get("pending_role")
        if pending:
            _, pin_col, _ = st.columns([1, 1.2, 1])
            with pin_col, st.container(border=True):
                with st.form("pin", border=False):
                    pin = st.text_input(f"PIN for {R.ROLES[pending].title}", type="password")
                    ok = st.form_submit_button("Enter workspace", type="primary", width="stretch")
                if ok:
                    if R.check_pin(pending, pin):
                        st.session_state.role = pending
                        st.session_state.pop("pending_role", None)
                        st.rerun()
                    st.error("Incorrect PIN.")
    st.stop()


# ====================================================================== sidebar
def sidebar(store: Store, role: R.Role) -> str | None:
    weeks = store.list_weeks()
    with st.sidebar:
        ui.sidebar_brand()
        ui.side_label("Workspace")
        st.markdown(f"{role.icon} **{role.title}**")
        if st.button("Switch role", icon=":material/swap_horiz:", type="tertiary"):
            for k in ("role", "pending_role"):
                st.session_state.pop(k, None)
            st.rerun()

        ui.side_label("Week")
        if weeks.empty:
            st.caption("No weeks analysed yet.")
            return None
        if "next_week" in st.session_state:
            st.session_state.week_id = st.session_state.pop("next_week")
        ids = list(weeks["week_id"])
        if st.session_state.get("week_id") not in ids:
            st.session_state.week_id = ids[0]
        labels = dict(zip(weeks["week_id"], weeks["label"], strict=True))
        week_id = st.selectbox(
            "Week", ids, key="week_id", format_func=lambda w: labels[w], label_visibility="collapsed"
        )
        row = weeks[weeks["week_id"] == week_id].iloc[0]
        st.caption(f"{row['reviews']} reviews · {row['source_name'] or 'manual'}")
        if pd.notna(row["emailed_at"]):
            st.caption(f":material/mark_email_read: Emailed {str(row['emailed_at'])[:10]}")

        ui.side_label("Configuration")
        st.caption(f"Model · `{settings.llm_model.split(':', 1)[-1]}`")
        st.caption(f"{len(weeks)} week(s) stored")
    return week_id


# ====================================================================== tabs
def overview_tab(df_ok: pd.DataFrame, stats: dict) -> None:
    c1, c2 = st.columns([2, 3], gap="medium")
    with c1, st.container(border=True):
        st.markdown("##### Sentiment split")
        st.altair_chart(charts.sentiment_donut(stats["sentiment_counts"]), width="stretch", theme=None)
    with c2, st.container(border=True):
        st.markdown("##### What customers talk about")
        st.altair_chart(charts.category_by_sentiment(df_ok), width="stretch", theme=None)
    c3, c4 = st.columns([3, 2], gap="medium")
    with c3, st.container(border=True):
        st.markdown("##### Daily volume by sentiment")
        st.altair_chart(charts.daily_trend(df_ok), width="stretch", theme=None)
    with c4, st.container(border=True):
        st.markdown("##### Platforms")
        st.altair_chart(charts.platform_by_sentiment(df_ok), width="stretch", theme=None)
    c5, c6 = st.columns([3, 2], gap="medium")
    with c5, st.container(border=True):
        st.markdown("##### Urgency")
        st.altair_chart(charts.urgency_bars(stats["urgency_counts"]), width="stretch", theme=None)
    with c6, st.container(border=True):
        st.markdown("##### Languages")
        total = max(stats["analysed"], 1)
        for lang in LANGUAGES:
            n = stats["language_counts"][lang]
            st.progress(n / total, text=f"{lang} · {n} ({100 * n / total:.0f}%)")


def trends_tab(store: Store, week_id: str) -> None:
    series = weekly_series(store.all_reviews())
    if len(series) < 2:
        st.info("Trends appear once at least two weeks are stored.", icon=":material/trending_up:")
        return
    cur = series["week"][series["week_id"] == week_id].iloc[0]
    c1, c2 = st.columns([3, 2], gap="medium")
    with c1, st.container(border=True):
        st.markdown("##### Sentiment share by week")
        st.altair_chart(charts.weekly_sentiment(series, cur), width="stretch", theme=None)
    with c2, st.container(border=True):
        st.markdown("##### Urgent reviews by week")
        st.altair_chart(charts.weekly_urgent(series), width="stretch", theme=None)
    with st.container(border=True):
        st.markdown("##### Complaints (negative reviews) by category and week")
        st.altair_chart(charts.complaints_heatmap(series), width="stretch", theme=None)

    rows = []
    prev = None
    for r in series.to_dict("records"):

        def arrow(key: str, higher_better: bool, unit: str = "", r=r, prev=prev) -> str:
            if prev is None:
                return f"{r[key]:.0f}{unit}"
            ch = r[key] - prev[key]
            sym = "▲" if ch > 0.05 else "▼" if ch < -0.05 else "▬"
            good = "🟢" if (ch > 0) == higher_better and abs(ch) > 0.05 else "🔴" if abs(ch) > 0.05 else "⚪"
            return f"{r[key]:.0f}{unit}  {sym}{abs(ch):.0f} {good}"

        rows.append(
            {
                "Week": r["week"],
                "Reviews": int(r["reviews"]),
                "Positive": arrow("positive_pct", True, "%"),
                "Negative": arrow("negative_pct", False, "%"),
                "Urgent": arrow("urgent", False),
                "Avg rating": f"{r['avg_rating']:.2f}",
            }
        )
        prev = r
    with st.container(border=True):
        st.markdown("##### Week-by-week")
        st.dataframe(pd.DataFrame(rows[::-1]), hide_index=True, width="stretch")


def urgent_tab(store: Store, role: R.Role, week_id: str, df: pd.DataFrame) -> None:
    urgent = df[(df["status"] == STATUS_OK) & (df["urgency"] == "high")]
    if urgent.empty:
        st.success("No HIGH-urgency reviews this week.")
        return
    done = int(urgent["handled"].sum())
    top, f1, f2 = st.columns([2, 3, 1.2], vertical_alignment="bottom")
    top.progress(done / len(urgent), text=f"**{done} of {len(urgent)}** urgent reviews handled")
    cats = f1.pills(
        "Category",
        [c for c in CATEGORIES if c in set(urgent["category"])],
        selection_mode="multi",
        format_func=lambda c: charts.CATEGORY_LABELS[c],
        label_visibility="collapsed",
    )
    hide_done = f2.toggle("Hide handled", value=False)
    view = urgent[urgent["category"].isin(cats)] if cats else urgent
    if hide_done:
        view = view[~view["handled"]]

    def on_handled(rid: str, value: bool) -> None:
        store.update_review(week_id, rid, {"handled": value}, allowed={"handled"})

    def on_save_reply(rid: str, reply: str, reply_en: str) -> None:
        store.update_review(week_id, rid, {"suggested_reply": reply, "reply_english": reply_en}, allowed=SUPPORT_FIELDS)
        st.toast(f"Reply for {rid} saved", icon=":material/check:")

    left, right = st.columns(2, gap="medium")
    for i, row in enumerate(view.to_dict("records")):
        with left if i % 2 == 0 else right:
            ui.urgent_card(
                row,
                can_handle=R.MARK_HANDLED in role.perms,
                can_edit=R.EDIT_REPLY in role.perms,
                on_handled=on_handled,
                on_save_reply=on_save_reply,
            )
    st.download_button(
        "Download urgent queue (CSV)",
        to_excel_csv(urgent),
        file_name=f"reviewlens_{week_id}_urgent.csv",
        mime="text/csv",
        icon=":material/download:",
    )


REVIEW_COLUMN_CONFIG = {
    "review_id": st.column_config.TextColumn("ID", pinned=True, width="small"),
    "date": st.column_config.DateColumn("Date", format="DD MMM", width="small"),
    "platform": st.column_config.TextColumn("Platform", width="small"),
    "rating": st.column_config.NumberColumn("Rating", format="%d ★", width="small"),
    "sentiment": st.column_config.SelectboxColumn("Sentiment", options=list(SENTIMENTS), width="small"),
    "urgency": st.column_config.SelectboxColumn("Urgency", options=list(URGENCIES), width="small"),
    "category": st.column_config.SelectboxColumn("Category", options=list(CATEGORIES), width="small"),
    "language": st.column_config.SelectboxColumn("Language", options=list(LANGUAGES), width="small"),
    "review_text": st.column_config.TextColumn("Review", width="large"),
    "summary": st.column_config.TextColumn("Summary (EN)", width="large"),
    "suggested_reply": st.column_config.TextColumn("Reply (customer's language)", width="large"),
    "reply_english": st.column_config.TextColumn("Reply (EN)", width="large"),
    "handled": st.column_config.CheckboxColumn("Handled", width="small"),
    "edited": st.column_config.CheckboxColumn("Edited", width="small", help="Changed by a person after AI tagging"),
    "status": st.column_config.TextColumn("Status", width="small"),
}
REVIEW_ORDER = list(REVIEW_COLUMN_CONFIG)


def reviews_tab(store: Store, role: R.Role, week_id: str, df: pd.DataFrame) -> None:
    with st.container(border=True):
        f = st.columns([2, 1, 1, 1, 1, 1])
        query = f[0].text_input("Search", placeholder="Search review text or summary", type="search")
        sent = f[1].multiselect("Sentiment", SENTIMENTS)
        cat = f[2].multiselect("Category", CATEGORIES, format_func=lambda c: charts.CATEGORY_LABELS[c])
        urg = f[3].multiselect("Urgency", URGENCIES)
        plat = f[4].multiselect("Platform", sorted(df["platform"].unique()))
        lang = f[5].multiselect("Language", LANGUAGES)
    view = df
    for col, sel in (("sentiment", sent), ("category", cat), ("urgency", urg), ("platform", plat), ("language", lang)):
        if sel:
            view = view[view[col].isin(sel)]
    if query:
        q = query.strip().lower()
        view = view[
            view["review_text"].str.lower().str.contains(q, regex=False)
            | view["summary"].astype(str).str.lower().str.contains(q, regex=False)
        ]

    if R.EDIT_ANALYSIS in role.perms:
        editable = EDITABLE_FIELDS | {"handled"}
    elif R.EDIT_REPLY in role.perms:
        editable = set(SUPPORT_FIELDS)
    else:
        editable = set()

    st.caption(
        f"Showing **{len(view)}** of {len(df)} reviews"
        + (f" · editable columns: {', '.join(sorted(editable))}" if editable else " · read-only")
    )
    if editable:
        edited = st.data_editor(
            view[REVIEW_ORDER],
            key=f"editor_{week_id}_{role.key}",
            width="stretch",
            height=520,
            hide_index=True,
            column_config=REVIEW_COLUMN_CONFIG,
            disabled=[c for c in REVIEW_ORDER if c not in editable],
            num_rows="fixed",
        )
        original = view[REVIEW_ORDER].set_index("review_id")
        changed = edited.set_index("review_id")
        diff = (original[sorted(editable)].astype(str) != changed[sorted(editable)].astype(str)).any(axis=1)
        n_changed = int(diff.sum())
        c1, c2 = st.columns([1, 4], vertical_alignment="center")
        if c1.button(f"Save {n_changed} change(s)", type="primary", disabled=n_changed == 0, icon=":material/save:"):
            for rid in diff[diff].index:
                changes = {
                    k: changed.at[rid, k] for k in editable if str(changed.at[rid, k]) != str(original.at[rid, k])
                }
                store.update_review(week_id, rid, changes, allowed=editable)
            st.toast(f"Saved {n_changed} review(s)", icon=":material/check:")
            st.session_state.pop(f"editor_{week_id}_{role.key}", None)
            st.rerun()
        if n_changed and R.MANAGE_WEEKS in role.perms:
            c2.caption("Counts update immediately; use Manage data → Regenerate report to refresh AI themes.")
    else:
        st.dataframe(
            view[REVIEW_ORDER], width="stretch", height=520, hide_index=True, column_config=REVIEW_COLUMN_CONFIG
        )

    c1, c2, _ = st.columns([1, 1, 2])
    c1.download_button(
        "Export all reviews (Excel CSV)",
        to_excel_csv(df),
        file_name=f"reviewlens_{week_id}_enriched.csv",
        mime="text/csv",
        type="primary",
        icon=":material/download:",
        width="stretch",
    )
    c2.download_button(
        "Export filtered view",
        to_excel_csv(view),
        file_name=f"reviewlens_{week_id}_filtered.csv",
        mime="text/csv",
        icon=":material/filter_alt:",
        width="stretch",
        disabled=len(view) == len(df),
    )


def report_tab(meta: dict, stats: dict, prev_stats: dict | None, prev_label: str) -> None:
    deltas = compare(stats, prev_stats) if prev_stats else None
    movers = category_complaint_deltas(stats, prev_stats) if prev_stats else None
    ui.report_view(stats, meta["insights"], date_range_label(stats), deltas, movers, prev_label)
    text = (
        render_report(stats, meta["insights"], prev_stats, prev_label)
        if meta["insights"]
        else meta["report_text"] or ""
    )
    c1, c2, _ = st.columns([1, 1, 3])
    c1.download_button(
        "Download report (.txt)",
        text.encode("utf-8"),
        file_name=f"reviewlens_{meta['week_id']}_report.txt",
        mime="text/plain",
        icon=":material/description:",
        width="stretch",
    )
    with c2.popover("Plain-text version", width="stretch"):
        st.code(text, language=None)


def data_tab(store: Store, role: R.Role, week_id: str | None) -> None:
    # ---------------- upload a new week
    with st.container(border=True):
        st.markdown("##### :material/upload_file: Upload & analyse a week")
        src = st.segmented_control("Source", ["Upload CSV", "Sample week"], default="Upload CSV", key="src_mode")
        source, source_name = None, ""
        if src == "Upload CSV":
            up = st.file_uploader("Weekly reviews CSV", type="csv", label_visibility="collapsed")
            if up is not None:
                source, source_name = up.getvalue(), up.name
            template = pd.DataFrame(columns=REQUIRED_COLUMNS).to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "CSV template",
                template,
                "reviewlens_template.csv",
                "text/csv",
                icon=":material/table:",
                type="tertiary",
            )
        else:
            pick = st.selectbox("Sample week", list(SAMPLE_WEEKS))
            source, source_name = str(SAMPLE_DIR / SAMPLE_WEEKS[pick]), SAMPLE_WEEKS[pick]

        if source is not None:
            try:
                loaded = load_reviews(source)
            except InvalidCSVError as exc:
                st.error(f"{exc}. Expected columns: {', '.join(REQUIRED_COLUMNS)}.")
                return
            new_id = week_id_for(loaded.df["date"])
            dates = pd.to_datetime(loaded.df["date"], errors="coerce").dropna()
            label = week_label(
                new_id,
                dates.min().date().isoformat() if not dates.empty else None,
                dates.max().date().isoformat() if not dates.empty else None,
            )
            exists = store.get_week(new_id) is not None
            st.markdown(f"**{label}** · {len(loaded.df)} reviews ready")
            notes = [f"{len(loaded.dropped)} row(s) removed during validation"] if loaded.dropped else []
            st.caption(" · ".join(notes + loaded.warnings) or "All rows passed validation.")
            if loaded.dropped:
                with st.expander("Removed rows"):
                    st.dataframe(pd.DataFrame(loaded.dropped), hide_index=True)
            replace = True
            if exists:
                replace = st.checkbox(
                    f"{new_id} already exists - replace it (manual edits and 'handled' marks will be lost)"
                )
            too_many = len(loaded.df) > MAX_ROWS
            if too_many:
                st.error(f"{len(loaded.df)} reviews exceeds the limit of {MAX_ROWS} per run.")
            if st.button(
                "Analyse & save week",
                type="primary",
                icon=":material/auto_awesome:",
                disabled=too_many or not replace,
            ):
                llm = llm_or_stop()
                with st.status(f"Analysing {len(loaded.df)} reviews…", expanded=True) as status:
                    st.write("Tagging sentiment, category, urgency; writing replies in each customer's language")
                    bar = st.progress(0.0)
                    saved = analyse_and_save(
                        store,
                        loaded.df,
                        llm,
                        source_name=source_name,
                        on_progress=lambda d, t: bar.progress(d / t, text=f"{d} / {t} reviews"),
                    )
                    status.update(label=f"{saved} analysed and saved", state="complete", expanded=False)
                st.session_state.next_week = saved
                st.rerun()

    if week_id is None:
        return
    meta = store.get_week(week_id)
    c1, c2 = st.columns(2, gap="medium")

    # ---------------- add one review
    with c1, st.container(border=True):
        st.markdown(f"##### :material/add_comment: Add a review to {meta['label'].split(' · ')[0]}")
        with st.form("add_review", clear_on_submit=True, border=False):
            a, b, c = st.columns(3)
            platform = a.selectbox("Platform", ["Google", "Zomato", "Swiggy", "Amazon", "Other"])
            rating = b.number_input("Rating", 1, 5, 3)
            day = c.date_input(
                "Date",
                value=pd.Timestamp(meta["date_to"]).date() if meta["date_to"] else date.today(),
            )
            text = st.text_area("Review text (English, Tamil or Tanglish)", height=90)
            if st.form_submit_button("Analyse & add", type="primary", icon=":material/auto_awesome:"):
                if not text.strip():
                    st.error("Review text is required.")
                else:
                    with st.spinner("Analysing…"):
                        try:
                            result = classify_one(llm_or_stop(), platform, int(rating), text.strip())
                        except Exception as exc:  # validation failures after retries
                            st.error(f"Could not analyse this review: {exc}")
                            st.stop()
                    rid = f"M-{pd.Timestamp.now():%m%d%H%M%S}"
                    store.add_review(
                        week_id,
                        {
                            "review_id": rid,
                            "date": day,
                            "platform": platform,
                            "rating": int(rating),
                            "review_text": text.strip(),
                            **result.model_dump(),
                            "status": STATUS_OK,
                        },
                    )
                    st.toast(f"Added {rid} · {result.sentiment} / {result.category} / {result.urgency}")

    # ---------------- maintain week
    with c2, st.container(border=True):
        st.markdown("##### :material/build: Maintain this week")
        st.caption("Rebuild the AI report after edits or added reviews (uses the previous week for trends).")
        if st.button("Regenerate report", icon=":material/refresh:"):
            with st.spinner("Writing the weekly report…"):
                regenerate_report(store, week_id, llm_or_stop())
            st.toast("Report regenerated", icon=":material/check:")
            st.rerun()
        st.divider()
        confirm = st.checkbox(f"I understand deleting {week_id} cannot be undone")
        if st.button("Delete week", icon=":material/delete:", disabled=not confirm):
            store.delete_week(week_id)
            st.session_state.pop("week_id", None)
            st.rerun()

    with st.container(border=True):
        st.markdown("##### Stored weeks")
        st.dataframe(
            store.list_weeks()[["label", "reviews", "source_name", "created_at", "emailed_at"]],
            hide_index=True,
            width="stretch",
            column_config={
                "label": "Week",
                "reviews": "Reviews",
                "source_name": "Source",
                "created_at": "Analysed (UTC)",
                "emailed_at": "Emailed (UTC)",
            },
        )


def email_tab(store: Store, role: R.Role, week_id: str | None) -> None:
    cfg = SMTPConfig.from_env()
    can_settings = R.EMAIL_SETTINGS in role.perms
    sched = schedule_config(store)

    c1, c2 = st.columns([3, 2], gap="medium")
    with c1, st.container(border=True):
        st.markdown("##### :material/schedule_send: Automatic weekly email")
        if cfg.configured:
            st.success(
                f"SMTP ready · sending as {cfg.sender} via {cfg.host}:{cfg.port}", icon=":material/check_circle:"
            )
        else:
            st.warning(
                "SMTP is not configured yet. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and SMTP_FROM "
                "in .env, then restart.",
                icon=":material/warning:",
            )
        with st.form("email_settings", border=False):
            to_text = st.text_area(
                "Recipients (comma or one per line)",
                ", ".join(recipients(store)),
                disabled=not can_settings,
                height=80,
            )
            a, b, c = st.columns([1, 1, 1])
            enabled = a.toggle("Send automatically", value=sched["enabled"], disabled=not can_settings)
            day = b.selectbox("Day", DAYS, index=DAYS.index(sched["day"]), disabled=not can_settings)
            hh, mm = (int(x) for x in sched["time"].split(":"))
            at = c.time_input(
                "Time", value=pd.Timestamp(2000, 1, 1, hh, mm).time(), disabled=not can_settings, step=900
            )
            saved = st.form_submit_button("Save settings", type="primary", disabled=not can_settings)
        if saved:
            store.set_setting(RECIPIENTS_KEY, ", ".join(parse_recipients(to_text)))
            store.set_setting(ENABLED_KEY, "1" if enabled else "0")
            store.set_setting(DAY_KEY, day)
            store.set_setting(TIME_KEY, at.strftime("%H:%M"))
            st.toast("Email settings saved", icon=":material/check:")
            st.rerun()
        st.caption(
            f"Schedule: {'every ' + sched['day'].title() + ' at ' + sched['time'] if sched['enabled'] else 'off'} "
            f"({sched['tz']}). Sends the latest analysed week; if it was already sent, a reminder to upload "
            "the new week goes out instead."
            + ("" if can_settings else " Only the Business Owner can change these settings.")
        )

    with c2, st.container(border=True):
        st.markdown("##### :material/send: Send now")
        if week_id is None:
            st.caption("No weeks to send yet.")
        else:
            to = recipients(store)
            st.caption(f"Sends the {week_id} report to {len(to)} recipient(s) with the enriched CSV attached.")
            if st.button(
                "Send report now",
                type="primary",
                icon=":material/send:",
                disabled=not (cfg.configured and to and R.SEND_EMAIL in role.perms),
                width="stretch",
            ):
                try:
                    with st.spinner("Sending…"):
                        msg = send_weekly_report(store, week_id, to, kind="manual", cfg=cfg)
                    st.success(msg)
                except Exception as exc:
                    st.error(f"Send failed: {exc}")
        st.markdown("##### Recent emails")
        log_df = store.email_log(10)
        if log_df.empty:
            st.caption("Nothing sent yet.")
        else:
            st.dataframe(log_df[["sent_at", "week_id", "kind", "status"]], hide_index=True, width="stretch")

    if week_id is not None:
        with st.expander("Preview the email", icon=":material/visibility:"):
            components.html(preview_html(store, week_id), height=1000, scrolling=True)


# ====================================================================== page
def main() -> None:
    store = get_store()
    role = role_gate()
    week_id = sidebar(store, role)

    if week_id is None:
        ui.page_header("Customer Feedback Intelligence", role.title, eyebrow="ReviewLens")
        if R.UPLOAD in role.perms:
            data_tab(store, role, None)
        else:
            ui.empty_state()
            st.info("No weeks have been analysed yet. The Operations Manager uploads each week's reviews.")
        ui.footer(settings.llm_model)
        return

    meta = store.get_week(week_id)
    df = store.get_reviews(week_id)
    stats = compute_stats(df)
    prev_id = store.previous_week_id(week_id)
    prev_stats = compute_stats(store.get_reviews(prev_id)) if prev_id else None
    prev_label = store.get_week(prev_id)["label"].split(" · ")[0] if prev_id else ""

    ui.page_header(
        meta["label"],
        f"{role.title} · {len(df)} reviews" + (f" · compared with {prev_label}" if prev_label else ""),
        eyebrow="Weekly feedback review",
    )
    ui.kpi_row(stats, compare(stats, prev_stats) if prev_stats else None, prev_label)
    if stats["needs_review"]:
        st.warning(
            f"{stats['needs_review']} review(s) could not be analysed after retries (status 'needs_review').",
            icon=":material/warning:",
        )
    st.space("small")

    titles = [R.TAB_TITLES[t] for t in role.tabs]
    if R.URGENT in role.tabs:
        titles[role.tabs.index(R.URGENT)] += f" ({stats['urgent']})"
    tabs = dict(zip(role.tabs, st.tabs(titles), strict=True))
    df_ok = df[df["status"] == STATUS_OK]
    for key, tab in tabs.items():
        with tab:
            if key == R.OVERVIEW:
                overview_tab(df_ok, stats)
            elif key == R.TRENDS:
                trends_tab(store, week_id)
            elif key == R.URGENT:
                urgent_tab(store, role, week_id, df)
            elif key == R.REVIEWS:
                reviews_tab(store, role, week_id, df)
            elif key == R.REPORT:
                report_tab(meta, stats, prev_stats, prev_label)
            elif key == R.DATA:
                data_tab(store, role, week_id)
            elif key == R.EMAIL:
                email_tab(store, role, week_id)
    ui.footer(settings.llm_model)


main()
