"""Render the weekly report text (brief section 1.6, Output B). All numbers come from pandas stats."""

from datetime import date

from reviewlens.schemas import Theme, WeeklyInsights

_LABEL_WIDTH = 26


def _fmt_date(d: date | None, with_year: bool) -> str:
    if d is None:
        return "?"
    return f"{d.day} {d:%b}" + (f" {d.year}" if with_year else "")


def _date_range(stats: dict) -> str:
    start, end = stats.get("date_from"), stats.get("date_to")
    if start is None or end is None:
        return "dates unknown"
    return f"{_fmt_date(start, start.year != end.year)} to {_fmt_date(end, True)}"


def _theme_line(n: int, theme: Theme) -> str:
    count = len(theme.review_ids)
    label = f"{theme.theme} ".ljust(_LABEL_WIDTH, ".")
    line = f"  {n}. {label} {count} review{'s' if count != 1 else ''}"
    return line + (f"  ({theme.note})" if theme.note else "")


def render_report(stats: dict, insights: WeeklyInsights) -> str:
    """Plain-text weekly report a manager can read in five minutes."""
    p = stats["sentiment_pct"]
    lines = [
        f"WEEKLY FEEDBACK REPORT  |  {_date_range(stats)}",
        f"Total reviews: {stats['total']}   Positive {p['positive']:.0f}%   "
        f"Neutral {p['neutral']:.0f}%   Negative {p['negative']:.0f}%",
    ]
    if stats["needs_review"]:
        lines.append(
            f"NOTE: {stats['needs_review']} review(s) could not be analysed and need manual review "
            f"(percentages are over the {stats['analysed']} analysed reviews)."
        )

    n_complaints = len(insights.top_complaints)
    lines += ["", f"TOP {n_complaints} COMPLAINTS" if n_complaints else "TOP COMPLAINTS"]
    lines += [_theme_line(i, t) for i, t in enumerate(insights.top_complaints, 1)] or ["  None this week."]

    lines += ["", "TOP PRAISE"]
    praise = [
        f"{t.theme} ({len(t.review_ids)} mention{'s' if len(t.review_ids) != 1 else ''})" for t in insights.top_praise
    ]
    lines.append(f"  {', '.join(praise)}" if praise else "  None this week.")

    urgent = stats["urgent"]
    lines += [
        "",
        f"URGENT: {urgent} review{'s' if urgent != 1 else ''} need{'s' if urgent == 1 else ''} a reply within 24 hours",
    ]

    lines += ["", "ACTION ITEMS"]
    lines += [f"  {i}. {a}" for i, a in enumerate(insights.action_items, 1)] or ["  None."]
    return "\n".join(lines)
