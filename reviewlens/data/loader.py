"""Read and validate the reviews CSV, then join LLM results onto it."""

import io
import logging
from dataclasses import dataclass, field
from typing import IO

import pandas as pd

from reviewlens.schemas import ANALYSIS_FIELDS, ReviewAnalysis

log = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["review_id", "date", "platform", "rating", "review_text"]
STATUS_OK = "ok"
STATUS_NEEDS_REVIEW = "needs_review"


class InvalidCSVError(ValueError):
    """Raised when the CSV cannot be used at all."""


@dataclass
class LoadResult:
    df: pd.DataFrame
    dropped: list[dict] = field(default_factory=list)  # {"review_id": ..., "reason": ...}
    warnings: list[str] = field(default_factory=list)


def _read_csv(source: str | bytes | IO) -> pd.DataFrame:
    if isinstance(source, bytes):
        raw = source
    elif hasattr(source, "read"):
        raw = source.read()
    else:
        with open(source, "rb") as f:
            raw = f.read()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, encoding=encoding)
        except UnicodeDecodeError:
            continue
        except pd.errors.ParserError as exc:
            raise InvalidCSVError(f"Could not parse CSV: {exc}") from exc
        except pd.errors.EmptyDataError as exc:
            raise InvalidCSVError("The CSV file is empty.") from exc
    raise InvalidCSVError("Could not decode the CSV. Please save it as UTF-8.")


def load_reviews(source: str | bytes | IO) -> LoadResult:
    """Read a reviews CSV and return clean rows plus a log of dropped rows."""
    df = _read_csv(source)
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise InvalidCSVError(f"Missing required column(s): {', '.join(missing)}")

    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    dropped: list[dict] = []
    warnings: list[str] = []

    empty = df["review_text"] == ""
    dropped += [{"review_id": rid, "reason": "empty review_text"} for rid in df.loc[empty, "review_id"]]
    df = df[~empty]

    no_id = df["review_id"] == ""
    dropped += [{"review_id": "(blank)", "reason": "missing review_id"} for _ in range(int(no_id.sum()))]
    df = df[~no_id]

    dup = df["review_id"].duplicated(keep="first")
    dropped += [{"review_id": rid, "reason": "duplicate review_id"} for rid in df.loc[dup, "review_id"]]
    df = df[~dup]

    if df.empty:
        raise InvalidCSVError("No usable reviews left after validation.")

    rating = pd.to_numeric(df["rating"], errors="coerce")
    bad_rating = rating.isna() | ~rating.between(1, 5)
    if bad_rating.any():
        warnings.append(f"{int(bad_rating.sum())} review(s) have a missing or invalid rating (kept).")
    df = df.assign(rating=rating.where(~bad_rating).astype("Int64"))

    dates = pd.to_datetime(df["date"], errors="coerce")
    if dates.isna().any():
        warnings.append(f"{int(dates.isna().sum())} review(s) have an unreadable date (kept).")
    df = df.assign(date=dates.dt.date)

    for d in dropped:
        log.info("dropped %s: %s", d["review_id"], d["reason"])
    return LoadResult(df=df.reset_index(drop=True), dropped=dropped, warnings=warnings)


def to_chain_inputs(df: pd.DataFrame) -> list[dict]:
    """Rows in the shape the classify prompt expects."""
    return [
        {
            "platform": r["platform"] or "unknown",
            "rating": "?" if pd.isna(r["rating"]) else int(r["rating"]),
            "review_text": r["review_text"],
        }
        for r in df.to_dict("records")
    ]


def enrich(df: pd.DataFrame, results: list[ReviewAnalysis | Exception]) -> pd.DataFrame:
    """Join per-row LLM results onto the input; failures become status='needs_review'."""
    if len(results) != len(df):
        raise ValueError(f"{len(results)} results for {len(df)} rows")
    records = []
    for res in results:
        if isinstance(res, ReviewAnalysis):
            records.append({**res.model_dump(), "status": STATUS_OK, "error": ""})
        else:
            records.append(
                {**dict.fromkeys(ANALYSIS_FIELDS, ""), "status": STATUS_NEEDS_REVIEW, "error": str(res)[:200]}
            )
    analysis = pd.DataFrame(records, index=df.index)
    return pd.concat([df, analysis], axis=1)
