"""Reduce step: weekly insights from all analysed reviews."""

import json

import pandas as pd
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable

from reviewlens.prompts import REPORT_PROMPT
from reviewlens.schemas import Theme, WeeklyInsights

_LINE_COLUMNS = ["review_id", "date", "platform", "rating", "sentiment", "category", "urgency", "language", "summary"]


def build_report_chain(llm: BaseChatModel) -> Runnable:
    """Prompt | model forced to return WeeklyInsights."""
    return REPORT_PROMPT | llm.with_structured_output(WeeklyInsights)


def _review_lines(df_ok: pd.DataFrame) -> str:
    rows = df_ok[_LINE_COLUMNS].astype(str).to_dict("records")
    return "\n".join(" | ".join(r[c] for c in _LINE_COLUMNS) for r in rows)


def _clean_themes(themes: list[Theme], known_ids: set[str]) -> list[Theme]:
    cleaned: list[Theme] = []
    for t in themes:
        ids = list(dict.fromkeys(i.strip() for i in t.review_ids if i.strip() in known_ids))
        if ids:
            cleaned.append(Theme(theme=t.theme.strip(), review_ids=ids, note=t.note.strip()))
    return sorted(cleaned, key=lambda t: len(t.review_ids), reverse=True)[:3]


def sanitize_insights(insights: WeeklyInsights, known_ids: set[str]) -> WeeklyInsights:
    """Drop invented or duplicate ids and empty themes; keep at most 3 themes and 3 actions."""
    return WeeklyInsights(
        top_complaints=_clean_themes(insights.top_complaints, known_ids),
        top_praise=_clean_themes(insights.top_praise, known_ids),
        action_items=[a.strip() for a in insights.action_items if a.strip()][:3],
    )


def generate_insights(chain: Runnable, df_ok: pd.DataFrame, stats: dict) -> WeeklyInsights:
    """Run the report chain over analysed rows and return sanitized insights."""
    if df_ok.empty:
        return WeeklyInsights(top_complaints=[], top_praise=[], action_items=[])
    raw = chain.invoke({"stats": json.dumps(stats, default=str, indent=1), "lines": _review_lines(df_ok)})
    return sanitize_insights(raw, set(df_ok["review_id"].astype(str)))
