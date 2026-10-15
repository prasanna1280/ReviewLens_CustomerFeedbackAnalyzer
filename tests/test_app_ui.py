"""Headless Streamlit tests for the three role workspaces (fake LLM, temp database)."""

from pathlib import Path

import pytest
import streamlit as st
from langchain_core.runnables import RunnableLambda
from streamlit.testing.v1 import AppTest

from reviewlens.schemas import Theme, WeeklyInsights
from tests.conftest import make_analysis

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def fake_classify(row):
    r = row["rating"] if isinstance(row["rating"], int) else 3
    if r >= 4:
        return make_analysis(sentiment="positive", category="food_quality", urgency="low")
    return make_analysis(category="packaging")


def fake_report(x):
    ids = [line.split(" | ")[0] for line in x["lines"].splitlines()]
    return WeeklyInsights(
        top_complaints=[Theme(theme="Leaking containers", review_ids=ids[:12], note="new containers")],
        top_praise=[Theme(theme="Biryani taste", review_ids=ids[12:20], note="")],
        action_items=["Switch container supplier", "Keep evening rider", "Reply to urgent reviews"],
    )


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "ui.db"))
    monkeypatch.setenv("SEED_DEMO", "1")
    for k in ("APP_PASSWORD", "ROLE_PIN_OWNER", "ROLE_PIN_MANAGER", "ROLE_PIN_SUPPORT", "SMTP_HOST"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("reviewlens.llm.get_llm", lambda *a, **k: object())
    monkeypatch.setattr("reviewlens.pipeline.build_classify_chain", lambda llm: RunnableLambda(fake_classify))
    monkeypatch.setattr("reviewlens.pipeline.build_report_chain", lambda llm: RunnableLambda(fake_report))
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def enter(role: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    [b for b in at.button if b.key == f"pick_{role}"][0].click().run()
    assert not at.exception, at.exception
    return at


def tab_labels(at: AppTest) -> list[str]:
    return [t.label.split(" ", 1)[1] for t in at.tabs]


def test_role_picker_then_owner_workspace(app_env):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert {b.key for b in at.button} >= {"pick_owner", "pick_manager", "pick_support"}
    at = enter("owner")
    assert tab_labels(at)[:2] == ["Weekly report", "Trends"] and "Manage data" not in tab_labels(at)
    labels = {m.label: m for m in at.metric}
    assert labels["Negative"].delta is not None  # W40 compared with W39
    assert any("Email" in t for t in tab_labels(at))


def test_support_workspace_is_limited(app_env):
    at = enter("support")
    assert tab_labels(at)[0].startswith("Urgent queue")
    assert "Manage data" not in tab_labels(at) and "Email" not in tab_labels(at)
    handled = [c for c in at.checkbox if c.key and c.key.startswith("handled_")]
    assert handled and not handled[0].disabled
    handled[0].check().run()
    assert not at.exception, at.exception


def test_manager_uploads_new_week_with_trends(app_env):
    at = enter("manager")
    assert "Manage data" in tab_labels(at)
    at.segmented_control(key="src_mode").set_value("Sample week").run()
    assert not at.exception, at.exception
    [b for b in at.button if b.label == "Analyse & save week"][0].click().run()
    assert not at.exception, at.exception
    assert at.session_state["week_id"] == "2026-W41"
    assert "Week 41" in at.html[1].value or any("Week 41" in h.value for h in at.html)
    labels = {m.label: m for m in at.metric}
    assert labels["Urgent"].delta is not None  # compared with W40
