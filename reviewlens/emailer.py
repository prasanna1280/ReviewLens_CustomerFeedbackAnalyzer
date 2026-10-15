"""Weekly report email: build (HTML + text + CSV attachment) and send over SMTP."""

import html
import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import reviewlens.config  # noqa: F401  (loads .env so SMTP_* settings are available)
from reviewlens.data.aggregate import compute_stats
from reviewlens.data.export import to_excel_csv
from reviewlens.report_render import render_report
from reviewlens.schemas import WeeklyInsights
from reviewlens.storage import Store
from reviewlens.trends import Delta, category_complaint_deltas, compare

log = logging.getLogger(__name__)

RECIPIENTS_KEY = "report_recipients"


@dataclass(frozen=True)
class SMTPConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str
    security: str  # starttls | ssl | none

    @classmethod
    def from_env(cls) -> "SMTPConfig":
        return cls(
            host=os.getenv("SMTP_HOST", ""),
            port=int(os.getenv("SMTP_PORT", "587")),
            user=os.getenv("SMTP_USER", ""),
            password=os.getenv("SMTP_PASSWORD", ""),
            sender=os.getenv("SMTP_FROM", "") or os.getenv("SMTP_USER", ""),
            security=os.getenv("SMTP_SECURITY", "starttls").lower(),
        )

    @property
    def configured(self) -> bool:
        return bool(self.host and self.sender)


def parse_recipients(text: str) -> list[str]:
    return [r.strip() for r in text.replace(";", ",").replace("\n", ",").split(",") if "@" in r]


def recipients(store: Store) -> list[str]:
    """Recipients saved in the app, falling back to REPORT_RECIPIENTS."""
    return parse_recipients(store.get_setting(RECIPIENTS_KEY) or os.getenv("REPORT_RECIPIENTS", ""))


# ------------------------------------------------------------------ HTML
_GOOD, _BAD, _MUTED = "#15803D", "#B91C1C", "#64748B"


def _delta_html(d: Delta) -> str:
    color = _MUTED if d.good is None else _GOOD if d.good else _BAD
    return (
        f'<span style="color:{color};font-size:12px">{html.escape(d.change_text())}</span>'
        if d.previous is not None
        else ""
    )


def _kpi_cell(label: str, value: str, d: Delta | None) -> str:
    return (
        '<td style="padding:12px 14px;border:1px solid #E2E8F0;background:#fff;width:20%">'
        f'<div style="font-size:11px;color:#64748B;text-transform:uppercase;letter-spacing:.05em">{label}</div>'
        f'<div style="font-size:22px;font-weight:700;color:#0F172A;margin:2px 0">{value}</div>'
        f"{_delta_html(d) if d else ''}</td>"
    )


def build_html(
    label: str, stats: dict, prev: dict | None, prev_label: str, insights: WeeklyInsights | None, app_url: str
) -> str:
    d = compare(stats, prev)
    p = stats["sentiment_pct"]
    avg = f"{stats['avg_rating']:.1f}★" if stats.get("avg_rating") is not None else "–"
    kpis = "".join(
        [
            _kpi_cell("Reviews", f"{stats['analysed']}", d["reviews"]),
            _kpi_cell("Positive", f"{p['positive']:.0f}%", d["positive"]),
            _kpi_cell("Negative", f"{p['negative']:.0f}%", d["negative"]),
            _kpi_cell("Urgent", f"{stats['urgent']}", d["urgent"]),
            _kpi_cell("Avg rating", avg, d["avg_rating"]),
        ]
    )
    sec = 'style="font-size:13px;font-weight:700;color:#1D4ED8;text-transform:uppercase;letter-spacing:.06em;margin:22px 0 8px"'
    td = 'style="padding:7px 10px;border-bottom:1px solid #E2E8F0;font-size:14px"'
    parts = [
        '<div style="font-family:Inter,Segoe UI,Arial,sans-serif;background:#F5F7FA;padding:24px">',
        '<div style="max-width:720px;margin:auto;background:#fff;border:1px solid #E2E8F0;border-radius:10px;overflow:hidden">',
        '<div style="background:#0F1B2D;color:#fff;padding:18px 24px">'
        '<div style="font-size:12px;color:#93C5FD;letter-spacing:.08em;text-transform:uppercase">ReviewLens · Weekly feedback report</div>'
        f'<div style="font-size:20px;font-weight:700;margin-top:4px">{html.escape(label)}</div></div>',
        '<div style="padding:20px 24px">',
        f'<table style="border-collapse:collapse;width:100%"><tr>{kpis}</tr></table>',
    ]
    if prev:
        parts.append(
            f'<div style="font-size:12px;color:#64748B;margin-top:6px">Arrows compare with {html.escape(prev_label)}.</div>'
        )
        movers = [m for m in category_complaint_deltas(stats, prev) if m.change][:4]
        if movers:
            rows = "".join(
                f"<tr><td {td}>{html.escape(m.label.replace('_', ' ').capitalize())}</td>"
                f"<td {td} align='right'>{m.current:g}</td><td {td} align='right'>{_delta_html(m)}</td></tr>"
                for m in movers
            )
            parts.append(
                f"<div {sec}>Complaint movers</div><table style='border-collapse:collapse;width:100%'>{rows}</table>"
            )
    if insights:
        if insights.top_complaints:
            rows = "".join(
                f"<tr><td {td}><b>{i}. {html.escape(t.theme)}</b><br><span style='color:#64748B;font-size:12px'>"
                f"{html.escape(t.note)}</span></td><td {td} align='right'>{len(t.review_ids)} reviews</td></tr>"
                for i, t in enumerate(insights.top_complaints, 1)
            )
            parts.append(
                f"<div {sec}>Top complaints</div><table style='border-collapse:collapse;width:100%'>{rows}</table>"
            )
        if insights.top_praise:
            praise = " · ".join(f"{html.escape(t.theme)} ({len(t.review_ids)})" for t in insights.top_praise)
            parts.append(f"<div {sec}>Top praise</div><div style='font-size:14px;color:#15803D'>{praise}</div>")
    parts.append(
        f"<div {sec}>Urgent</div><div style='font-size:14px'><b style='color:#B91C1C'>{stats['urgent']} reviews</b> "
        "need a reply within 24 hours. Suggested replies are ready in the Urgent queue.</div>"
    )
    if insights and insights.action_items:
        items = "".join(f"<li style='margin:4px 0'>{html.escape(a)}</li>" for a in insights.action_items)
        parts.append(f"<div {sec}>Action items</div><ol style='font-size:14px;padding-left:20px;margin:0'>{items}</ol>")
    if app_url:
        parts.append(
            f'<div style="margin-top:22px"><a href="{html.escape(app_url)}" style="background:#1D4ED8;color:#fff;'
            'padding:10px 16px;border-radius:6px;text-decoration:none;font-size:14px">Open ReviewLens</a></div>'
        )
    parts.append(
        '<div style="font-size:11px;color:#94A3B8;margin-top:22px">Counts and percentages are calculated from the data; '
        "themes and actions are AI-generated. Full enriched table attached (opens in Excel).</div></div></div></div>"
    )
    return "".join(parts)


# ------------------------------------------------------------------ build + send
def build_weekly_message(store: Store, week_id: str, to: list[str], cfg: SMTPConfig, app_url: str = "") -> EmailMessage:
    meta = store.get_week(week_id)
    if meta is None:
        raise ValueError(f"Unknown week {week_id}")
    df = store.get_reviews(week_id)
    stats = compute_stats(df)
    prev_id = store.previous_week_id(week_id)
    prev_meta = store.get_week(prev_id) if prev_id else None
    prev_stats = compute_stats(store.get_reviews(prev_id)) if prev_id else None
    prev_label = prev_meta["label"].split(" · ")[0] if prev_meta else "last week"
    insights: WeeklyInsights | None = meta["insights"]

    msg = EmailMessage()
    p = stats["sentiment_pct"]
    msg["Subject"] = (
        f"ReviewLens weekly report · {meta['label']} · {stats['urgent']} urgent · {p['negative']:.0f}% negative"
    )
    msg["From"] = cfg.sender
    msg["To"] = ", ".join(to)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=cfg.sender.split("@")[-1] if "@" in cfg.sender else None)
    text = (
        render_report(stats, insights, prev_stats, prev_label)
        if insights
        else (meta.get("report_text") or "Report not available.")
    )
    msg.set_content(text + (f"\n\nOpen ReviewLens: {app_url}" if app_url else ""))
    msg.add_alternative(build_html(meta["label"], stats, prev_stats, prev_label, insights, app_url), subtype="html")
    msg.add_attachment(to_excel_csv(df), maintype="text", subtype="csv", filename=f"reviewlens_{week_id}_enriched.csv")
    return msg


def build_reminder_message(latest_label: str, to: list[str], cfg: SMTPConfig, app_url: str = "") -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "ReviewLens · this week's reviews have not been uploaded yet"
    msg["From"] = cfg.sender
    msg["To"] = ", ".join(to)
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(
        f"No new week has been analysed since {latest_label}, so there is no new weekly report.\n"
        "Operations manager: please upload this week's reviews in ReviewLens." + (f"\n\n{app_url}" if app_url else "")
    )
    return msg


def send_message(msg: EmailMessage, cfg: SMTPConfig) -> None:
    if not cfg.configured:
        raise RuntimeError("SMTP is not configured (set SMTP_HOST and SMTP_FROM / SMTP_USER in .env).")
    ctx = ssl.create_default_context()
    if cfg.security == "ssl":
        server: smtplib.SMTP = smtplib.SMTP_SSL(cfg.host, cfg.port, context=ctx, timeout=30)
    else:
        server = smtplib.SMTP(cfg.host, cfg.port, timeout=30)
    with server:
        if cfg.security == "starttls":
            server.starttls(context=ctx)
        if cfg.user and cfg.password:
            server.login(cfg.user, cfg.password)
        server.send_message(msg)


def send_weekly_report(
    store: Store,
    week_id: str | None = None,
    to: list[str] | None = None,
    kind: str = "weekly",
    cfg: SMTPConfig | None = None,
) -> str:
    """Send one week's report (default: latest) and log the outcome. Returns a status message."""
    cfg = cfg or SMTPConfig.from_env()
    to = to or recipients(store)
    week_id = week_id or store.latest_week_id()
    app_url = os.getenv("APP_URL", "")
    if not to:
        raise RuntimeError("No recipients configured.")
    if not week_id:
        raise RuntimeError("No analysed weeks yet.")
    try:
        send_message(build_weekly_message(store, week_id, to, cfg, app_url), cfg)
    except Exception as exc:
        store.log_email(week_id, to, kind, "failed", str(exc))
        log.exception("weekly email failed")
        raise
    store.log_email(week_id, to, kind, "sent")
    return f"Weekly report for {week_id} sent to {len(to)} recipient(s)."


def run_scheduled(store: Store, cfg: SMTPConfig | None = None) -> str:
    """Monday job: send the latest week, or a reminder if it was already sent."""
    cfg = cfg or SMTPConfig.from_env()
    to = recipients(store)
    if not to:
        return "skipped: no recipients"
    latest = store.latest_week_id()
    if not latest:
        return "skipped: no analysed weeks"
    weeks = store.list_weeks()
    already = weeks.loc[weeks["week_id"] == latest, "emailed_at"].notna().any()
    if not already:
        return send_weekly_report(store, latest, to, kind="weekly", cfg=cfg)
    label = weeks.loc[weeks["week_id"] == latest, "label"].iloc[0]
    try:
        send_message(build_reminder_message(label, to, cfg, os.getenv("APP_URL", "")), cfg)
        store.log_email(latest, to, "reminder", "sent")
    except Exception as exc:
        store.log_email(latest, to, "reminder", "failed", str(exc))
        raise
    return f"reminder sent (latest week {latest} was already emailed)"


def preview_html(store: Store, week_id: str) -> str:
    """HTML body for in-app preview."""
    meta = store.get_week(week_id)
    stats = compute_stats(store.get_reviews(week_id))
    prev_id = store.previous_week_id(week_id)
    prev = compute_stats(store.get_reviews(prev_id)) if prev_id else None
    prev_label = store.get_week(prev_id)["label"].split(" · ")[0] if prev_id else "last week"
    return build_html(meta["label"], stats, prev, prev_label, meta["insights"], os.getenv("APP_URL", ""))
