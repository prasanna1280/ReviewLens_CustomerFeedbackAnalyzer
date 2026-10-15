from datetime import datetime

import pytest

from reviewlens import roles as R
from reviewlens.emailer import SMTPConfig, build_weekly_message, parse_recipients, run_scheduled, send_weekly_report
from reviewlens.pipeline import import_history
from reviewlens.scheduler import LAST_RUN_KEY, is_due, tick
from reviewlens.storage import Store


# ------------------------------------------------------------------ roles
def test_permission_matrix():
    assert R.can("manager", R.UPLOAD) and R.can("manager", R.EDIT_ANALYSIS)
    assert not R.can("support", R.UPLOAD) and not R.can("support", R.EDIT_ANALYSIS)
    assert R.can("support", R.EDIT_REPLY) and R.can("support", R.MARK_HANDLED)
    assert R.can("owner", R.EMAIL_SETTINGS) and not R.can("owner", R.UPLOAD)
    assert not R.can("manager", R.EMAIL_SETTINGS)
    assert not R.can(None, R.VIEW) and not R.can("intruder", R.VIEW)
    assert R.DATA in R.ROLES["manager"].tabs and R.DATA not in R.ROLES["support"].tabs


def test_role_pins(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("ROLE_PIN_MANAGER", raising=False)
    assert R.check_pin("manager", "")  # no PIN configured
    monkeypatch.setenv("APP_PASSWORD", "shared")
    assert R.check_pin("support", "shared") and not R.check_pin("support", "x")
    monkeypatch.setenv("ROLE_PIN_MANAGER", "4321")
    assert R.check_pin("manager", "4321") and not R.check_pin("manager", "shared")


# ------------------------------------------------------------------ email
class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


CFG = SMTPConfig("smtp.test", 587, "u", "p", "reports@test.com", "starttls")


@pytest.fixture
def store(tmp_path, monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr("reviewlens.emailer.smtplib.SMTP", FakeSMTP)
    s = Store(tmp_path / "e.db")
    import_history(s)
    return s


def test_parse_recipients():
    assert parse_recipients("a@x.com, b@y.com;c@z.com\nnot-an-email") == ["a@x.com", "b@y.com", "c@z.com"]


def test_weekly_message_has_trends_html_and_attachment(store):
    msg = build_weekly_message(store, "2026-W40", ["boss@x.com"], CFG, "https://app")
    assert "Week 40" in msg["Subject"] and "urgent" in msg["Subject"]
    parts = {p.get_content_type(): p for p in msg.walk()}
    assert "text/html" in parts and "text/plain" in parts and "text/csv" in parts
    html = parts["text/html"].get_content()
    assert "Arrows compare with Week 39" in html and "Open ReviewLens" in html
    assert "VS WEEK 39" in parts["text/plain"].get_content()


def test_send_logs_and_marks_week(store):
    msg = send_weekly_report(store, "2026-W40", ["boss@x.com"], cfg=CFG)
    assert "sent to 1" in msg and len(FakeSMTP.sent) == 1
    weeks = store.list_weeks().set_index("week_id")
    assert weeks.loc["2026-W40", "emailed_at"] is not None


def test_scheduled_sends_once_then_reminds(store):
    store.set_setting("report_recipients", "boss@x.com")
    assert "sent" in run_scheduled(store, CFG)
    assert "reminder" in run_scheduled(store, CFG)
    assert "not been uploaded" in FakeSMTP.sent[-1]["Subject"]


def test_scheduler_due_once_per_day(store, monkeypatch):
    monkeypatch.setattr("reviewlens.scheduler.run_scheduled", lambda s: "ok")
    cfg = {"enabled": True, "day": "MON", "time": "09:00", "last_run": ""}
    monday_8 = datetime(2026, 10, 19, 8, 59)
    monday_9 = datetime(2026, 10, 19, 9, 0)
    assert not is_due(cfg, monday_8) and is_due(cfg, monday_9)
    assert not is_due({**cfg, "enabled": False}, monday_9)
    assert not is_due(cfg, datetime(2026, 10, 20, 9, 0))  # Tuesday
    assert tick(store, monday_9) == "ok"
    assert store.get_setting(LAST_RUN_KEY) == "2026-10-19"
    assert tick(store, datetime(2026, 10, 19, 15, 0)) is None  # already ran today


def test_capability_cards_list_same_rows_for_every_role():
    rows = {k: R.capabilities(k) for k in R.ROLES}
    labels = {tuple(label for label, _ in caps) for caps in rows.values()}
    assert len(labels) == 1  # identical rows -> equal card heights
    allowed = {k: {label for label, ok in caps if ok} for k, caps in rows.items()}
    assert "Upload weekly reviews" in allowed["manager"] and "Upload weekly reviews" not in allowed["support"]
    assert "Set email schedule" in allowed["owner"] and "Set email schedule" not in allowed["manager"]
    assert allowed["support"] == {"Weekly report", "Reply to urgent reviews"}
