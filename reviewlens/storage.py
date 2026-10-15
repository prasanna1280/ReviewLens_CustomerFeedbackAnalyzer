"""SQLite store for analysed weeks, reviews, settings and the email log."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from reviewlens.schemas import ANALYSIS_FIELDS, WeeklyInsights

DEFAULT_DB = Path(__file__).resolve().parent.parent / "storage" / "reviewlens.db"

REVIEW_COLUMNS = [
    "review_id",
    "date",
    "platform",
    "rating",
    "review_text",
    *ANALYSIS_FIELDS,
    "status",
    "error",
    "handled",
    "edited",
]
EDITABLE_FIELDS = {"sentiment", "category", "urgency", "language", "summary", "suggested_reply", "reply_english"}
SUPPORT_FIELDS = {"suggested_reply", "reply_english", "handled"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS weeks (
    week_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    date_from TEXT,
    date_to TEXT,
    source_name TEXT,
    model TEXT,
    insights_json TEXT,
    report_text TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    week_id TEXT NOT NULL REFERENCES weeks(week_id) ON DELETE CASCADE,
    review_id TEXT NOT NULL,
    date TEXT, platform TEXT, rating INTEGER, review_text TEXT,
    sentiment TEXT, category TEXT, urgency TEXT, language TEXT,
    summary TEXT, suggested_reply TEXT, reply_english TEXT,
    status TEXT, error TEXT,
    handled INTEGER NOT NULL DEFAULT 0,
    edited INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT,
    PRIMARY KEY (week_id, review_id)
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS email_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_id TEXT, sent_at TEXT NOT NULL, recipients TEXT, kind TEXT, status TEXT, error TEXT
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def week_id_for(dates: pd.Series) -> str:
    """ISO week of the median review date, e.g. '2026-W40'."""
    d = pd.to_datetime(dates, errors="coerce").dropna()
    if d.empty:
        d = pd.Series([pd.Timestamp.today()])
    iso = d.sort_values().iloc[len(d) // 2].isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def week_label(week_id: str, date_from: str | None, date_to: str | None) -> str:
    """'Week 40 · 29 Sep – 5 Oct 2026'."""
    num = int(week_id.split("-W")[1])
    if not date_from or not date_to:
        return f"Week {num}"
    a, b = pd.Timestamp(date_from), pd.Timestamp(date_to)
    return f"Week {num} · {a.day} {a:%b} – {b.day} {b:%b %Y}"


class Store:
    """Thin repository over SQLite. A new connection per call keeps it thread-safe for Streamlit."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.getenv("DB_PATH") or DEFAULT_DB)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------ weeks
    def save_week(
        self,
        week_id: str,
        enriched: pd.DataFrame,
        insights: WeeklyInsights | None,
        report_text: str,
        source_name: str = "",
        model: str = "",
    ) -> None:
        """Insert or fully replace a week and its reviews."""
        dates = pd.to_datetime(enriched["date"], errors="coerce").dropna()
        date_from = dates.min().date().isoformat() if not dates.empty else None
        date_to = dates.max().date().isoformat() if not dates.empty else None
        now = _now()
        rows = [self._review_row(week_id, r, now) for r in enriched.to_dict("records")]
        with self._conn() as c:
            c.execute("DELETE FROM weeks WHERE week_id = ?", (week_id,))
            c.execute(
                "INSERT INTO weeks VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    week_id,
                    week_label(week_id, date_from, date_to),
                    date_from,
                    date_to,
                    source_name,
                    model,
                    insights.model_dump_json() if insights else None,
                    report_text,
                    now,
                    now,
                ),
            )
            c.executemany(f"INSERT INTO reviews VALUES ({','.join('?' * 18)})", rows)

    @staticmethod
    def _review_row(week_id: str, r: dict, now: str) -> tuple:
        rating = r.get("rating")
        rating = None if rating is None or pd.isna(rating) else int(rating)
        d = r.get("date")
        d = None if d is None or pd.isna(d) else pd.Timestamp(d).date().isoformat()
        text = [str(r.get(f) or "") for f in ANALYSIS_FIELDS]
        return (
            week_id,
            str(r["review_id"]),
            d,
            str(r.get("platform") or ""),
            rating,
            str(r.get("review_text") or ""),
            *text,
            str(r.get("status") or ""),
            str(r.get("error") or ""),
            int(bool(r.get("handled", 0))),
            int(bool(r.get("edited", 0))),
            now,
        )

    def list_weeks(self) -> pd.DataFrame:
        """All weeks, newest first, with review counts."""
        with self._conn() as c:
            return pd.read_sql_query(
                "SELECT w.week_id, w.label, w.date_from, w.date_to, w.source_name, w.created_at, "
                "COUNT(r.review_id) AS reviews, "
                "(SELECT MAX(sent_at) FROM email_log e WHERE e.week_id = w.week_id AND e.status = 'sent' "
                " AND e.kind = 'weekly') AS emailed_at "
                "FROM weeks w LEFT JOIN reviews r ON r.week_id = w.week_id "
                "GROUP BY w.week_id ORDER BY w.week_id DESC",
                c,
            )

    def get_week(self, week_id: str) -> dict | None:
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            row = c.execute("SELECT * FROM weeks WHERE week_id = ?", (week_id,)).fetchone()
        if row is None:
            return None
        meta = dict(row)
        meta["insights"] = WeeklyInsights.model_validate_json(meta["insights_json"]) if meta["insights_json"] else None
        return meta

    def previous_week_id(self, week_id: str) -> str | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT week_id FROM weeks WHERE week_id < ? ORDER BY week_id DESC LIMIT 1", (week_id,)
            ).fetchone()
        return row[0] if row else None

    def latest_week_id(self) -> str | None:
        with self._conn() as c:
            row = c.execute("SELECT MAX(week_id) FROM weeks").fetchone()
        return row[0] if row and row[0] else None

    def set_report(self, week_id: str, insights: WeeklyInsights | None, report_text: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE weeks SET insights_json = ?, report_text = ?, updated_at = ? WHERE week_id = ?",
                (insights.model_dump_json() if insights else None, report_text, _now(), week_id),
            )

    def delete_week(self, week_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM weeks WHERE week_id = ?", (week_id,))

    # ------------------------------------------------------------ reviews
    def get_reviews(self, week_id: str) -> pd.DataFrame:
        with self._conn() as c:
            df = pd.read_sql_query(
                f"SELECT {', '.join(REVIEW_COLUMNS)} FROM reviews WHERE week_id = ? ORDER BY date, review_id",
                c,
                params=(week_id,),
            )
        df["rating"] = df["rating"].astype("Int64")
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        df["handled"] = df["handled"].astype(bool)
        df["edited"] = df["edited"].astype(bool)
        return df

    def all_reviews(self) -> pd.DataFrame:
        """Every stored review with its week id (for multi-week trends)."""
        with self._conn() as c:
            return pd.read_sql_query(
                "SELECT week_id, sentiment, category, urgency, language, rating, status FROM reviews", c
            )

    def update_review(self, week_id: str, review_id: str, changes: dict, allowed: set[str] | None = None) -> None:
        """Update whitelisted fields of one review; analysis edits flag the row as edited."""
        allowed = allowed or (EDITABLE_FIELDS | {"handled"})
        fields = {k: v for k, v in changes.items() if k in allowed}
        if not fields:
            return
        if "handled" in fields:
            fields["handled"] = int(bool(fields["handled"]))
        sets = ", ".join(f"{k} = ?" for k in fields)
        edited = ", edited = 1" if set(fields) & EDITABLE_FIELDS else ""
        with self._conn() as c:
            c.execute(
                f"UPDATE reviews SET {sets}{edited}, updated_at = ? WHERE week_id = ? AND review_id = ?",
                (*fields.values(), _now(), week_id, review_id),
            )

    def add_review(self, week_id: str, row: dict) -> None:
        with self._conn() as c:
            c.execute(
                f"INSERT OR REPLACE INTO reviews VALUES ({','.join('?' * 18)})",
                self._review_row(week_id, {**row, "edited": True}, _now()),
            )
            c.execute("UPDATE weeks SET updated_at = ? WHERE week_id = ?", (_now(), week_id))

    # ------------------------------------------------------------ settings + email log
    def get_setting(self, key: str, default: str = "") -> str:
        with self._conn() as c:
            row = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, value))

    def log_email(self, week_id: str | None, recipients: list[str], kind: str, status: str, error: str = "") -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO email_log (week_id, sent_at, recipients, kind, status, error) VALUES (?,?,?,?,?,?)",
                (week_id, _now(), json.dumps(recipients), kind, status, error[:500]),
            )

    def email_log(self, limit: int = 20) -> pd.DataFrame:
        with self._conn() as c:
            return pd.read_sql_query(
                "SELECT sent_at, week_id, kind, status, recipients, error FROM email_log ORDER BY id DESC LIMIT ?",
                c,
                params=(limit,),
            )
