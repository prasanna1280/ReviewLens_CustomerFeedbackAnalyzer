"""Chat model factory - the only provider-aware module."""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from reviewlens.config import settings


class LLMConfigError(RuntimeError):
    """Raised when the model cannot be created (bad LLM_MODEL or missing key)."""


def get_llm(model: str | None = None) -> BaseChatModel:
    """Build the chat model named by LLM_MODEL, e.g. 'openai:gpt-5.4-mini'."""
    name = model or settings.llm_model
    try:
        return init_chat_model(name, temperature=0, max_retries=3, timeout=60)
    except Exception as exc:  # provider packages raise various types
        raise LLMConfigError(f"Could not create model '{name}': {exc}") from exc
