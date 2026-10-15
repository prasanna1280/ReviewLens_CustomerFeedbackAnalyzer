import re
from pathlib import Path

from reviewlens.config import load_settings

ROOT = Path(__file__).resolve().parent.parent


def test_settings_read_from_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "openai:test-model")
    monkeypatch.setenv("MAX_CONCURRENCY", "3")
    s = load_settings()
    assert s.llm_model == "openai:test-model" and s.max_concurrency == 3


def test_no_hardcoded_api_keys():
    pattern = re.compile(r"(sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|sk-ant-[A-Za-z0-9_-]{20,})")
    files = [ROOT / "app.py", *(ROOT / "reviewlens").rglob("*.py"), ROOT / ".env.example"]
    for f in files:
        assert not pattern.search(f.read_text(encoding="utf-8")), f
