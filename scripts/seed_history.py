"""Analyse sample weeks with the real LLM and export them as demo history.

Usage:
  python scripts/seed_history.py                # analyse W38, W39, W40 -> data/sample/history/
  python scripts/seed_history.py --weeks 38 39  # specific weeks

The exported CSV + JSON files are committed, so any fresh install (incl. the VPS) shows three
weeks of history without spending tokens. W41 is left raw for a live upload demo.
"""

import argparse
import logging
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reviewlens.data.loader import load_reviews  # noqa: E402
from reviewlens.llm import get_llm  # noqa: E402
from reviewlens.pipeline import HISTORY_DIR, analyse_and_save, export_week  # noqa: E402
from reviewlens.storage import Store  # noqa: E402

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", nargs="+", type=int, default=[38, 39, 40])
    args = ap.parse_args()

    llm = get_llm()
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "seed.db")
        for week in sorted(args.weeks):  # oldest first so each week sees the previous one
            name = "reviews_week40_full.csv" if week == 40 else f"reviews_week{week}.csv"
            df = load_reviews(str(SAMPLE / name)).df
            t = time.time()
            week_id = analyse_and_save(store, df, llm, source_name=name)
            reviews = store.get_reviews(week_id)
            bad = int((reviews["status"] != "ok").sum())
            print(f"{week_id}: {len(reviews)} reviews, {bad} needs_review, {time.time() - t:.0f}s")
            export_week(store, week_id, HISTORY_DIR)
    print(f"exported to {HISTORY_DIR}")


if __name__ == "__main__":
    main()
