"""Settings loaded from environment / .env (never hard-code keys)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "openai:gpt-5.4-mini"


@dataclass(frozen=True)
class Settings:
    llm_model: str
    max_concurrency: int
    max_retries: int
    chunk_size: int


def load_settings() -> Settings:
    """Read settings from the environment."""
    return Settings(
        llm_model=os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODEL,
        max_concurrency=int(os.getenv("MAX_CONCURRENCY", "5")),
        max_retries=int(os.getenv("MAX_RETRIES", "2")),
        chunk_size=int(os.getenv("CHUNK_SIZE", "25")),
    )


settings = load_settings()
