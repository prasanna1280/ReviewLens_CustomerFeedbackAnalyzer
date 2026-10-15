"""End-to-end week processing shared by the app, scripts and scheduler."""

import json
import logging
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from langchain_core.language_models import BaseChatModel

from reviewlens.chains.classify import build_classify_chain, classify_reviews
from reviewlens.chains.report import build_report_chain, generate_insights
from reviewlens.config import settings
from reviewlens.data.aggregate import compute_stats
from reviewlens.data.loader import STATUS_OK, enrich, to_chain_inputs
from reviewlens.report_render import render_report
from reviewlens.schemas import ReviewAnalysis, WeeklyInsights
from reviewlens.storage import Store, week_id_for
from reviewlens.trends import trend_text

log = logging.getLogger(__name__)

HISTORY_DIR = Path(__file__).resolve().parent.parent / "data" / "sample" / "history"


def previous_context(store: Store, week_id: str) -> tuple[dict | None, str]:
    """Stats and short label of the stored week before week_id."""
    prev_id = store.previous_week_id(week_id)
    if not prev_id:
        return None, "last week"
    meta = store.get_week(prev_id)
    return compute_stats(store.get_reviews(prev_id)), meta["label"].split(" · ")[0]


def build_report(
    store: Store, week_id: str, enriched: pd.DataFrame, llm: BaseChatModel
) -> tuple[WeeklyInsights | None, str]:
    """Run the report chain (with last-week context) and render the text."""
    stats = compute_stats(enriched)
    prev_stats, prev_label = previous_context(store, week_id)
    try:
        insights = generate_insights(
            build_report_chain(llm),
            enriched[enriched["status"] == STATUS_OK],
            stats,
            trend_text(stats, prev_stats, prev_label),
        )
        return insights, render_report(stats, insights, prev_stats, prev_label)
    except Exception:
        log.exception("report chain failed")
        return None, "The weekly report could not be generated. Use 'Regenerate report' to try again."


def analyse_and_save(
    store: Store,
    loaded_df: pd.DataFrame,
    llm: BaseChatModel,
    source_name: str = "",
    on_progress: Callable[[int, int], None] | None = None,
    week_id: str | None = None,
) -> str:
    """Classify a validated week, write its report and store it. Returns the week id."""
    week_id = week_id or week_id_for(loaded_df["date"])
    results = classify_reviews(
        build_classify_chain(llm),
        to_chain_inputs(loaded_df),
        max_concurrency=settings.max_concurrency,
        max_retries=settings.max_retries,
        on_progress=on_progress,
        chunk_size=settings.chunk_size,
    )
    enriched = enrich(loaded_df, results)
    insights, report_text = build_report(store, week_id, enriched, llm)
    store.save_week(week_id, enriched, insights, report_text, source_name, settings.llm_model)
    return week_id


def regenerate_report(store: Store, week_id: str, llm: BaseChatModel) -> None:
    """Rebuild a stored week's report from its current (possibly edited) reviews."""
    insights, text = build_report(store, week_id, store.get_reviews(week_id), llm)
    store.set_report(week_id, insights, text)


def classify_one(llm: BaseChatModel, platform: str, rating: int | None, text: str) -> ReviewAnalysis:
    """Analyse a single manually added review (with the usual retry)."""
    row = {"platform": platform or "unknown", "rating": "?" if rating is None else rating, "review_text": text}
    result = classify_reviews(build_classify_chain(llm), [row], 1, settings.max_retries)[0]
    if isinstance(result, Exception):
        raise result
    return result


# ------------------------------------------------------------------ demo history (no LLM needed to load)
def export_week(store: Store, week_id: str, out_dir: Path = HISTORY_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = store.get_week(week_id)
    store.get_reviews(week_id).to_csv(out_dir / f"{week_id}.csv", index=False, encoding="utf-8")
    (out_dir / f"{week_id}.json").write_text(
        json.dumps(
            {
                "week_id": week_id,
                "source_name": meta["source_name"],
                "model": meta["model"],
                "insights": json.loads(meta["insights_json"]) if meta["insights_json"] else None,
                "report_text": meta["report_text"],
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


def import_history(store: Store, src_dir: Path = HISTORY_DIR) -> list[str]:
    """Load pre-analysed demo weeks into an empty store."""
    loaded = []
    for meta_file in sorted(src_dir.glob("*.json")):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        df = pd.read_csv(src_dir / f"{meta['week_id']}.csv", dtype={"review_id": str}, keep_default_na=False)
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce").astype("Int64")
        insights = WeeklyInsights.model_validate(meta["insights"]) if meta.get("insights") else None
        store.save_week(meta["week_id"], df, insights, meta["report_text"], meta["source_name"], meta["model"])
        loaded.append(meta["week_id"])
    return loaded


def ensure_demo_history(store: Store) -> list[str]:
    """Seed demo weeks once, when the store is empty and SEED_DEMO is not disabled."""
    import os

    if os.getenv("SEED_DEMO", "1") == "0" or store.latest_week_id() or not HISTORY_DIR.exists():
        return []
    weeks = import_history(store)
    log.info("seeded demo history: %s", weeks)
    return weeks
