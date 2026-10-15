"""Map step: classify each review with structured output, batching and retry."""

import logging
from collections.abc import Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable

from reviewlens.prompts import CLASSIFY_PROMPT
from reviewlens.schemas import ReviewAnalysis

log = logging.getLogger(__name__)

ProgressFn = Callable[[int, int], None]


def build_classify_chain(llm: BaseChatModel) -> Runnable:
    """Prompt | model forced to return a ReviewAnalysis."""
    return CLASSIFY_PROMPT | llm.with_structured_output(ReviewAnalysis)


def _run_batch(
    chain: Runnable, rows: list[dict], max_concurrency: int, max_retries: int
) -> list[ReviewAnalysis | Exception]:
    results: list[ReviewAnalysis | Exception] = [RuntimeError("not processed")] * len(rows)
    pending = list(range(len(rows)))
    for attempt in range(max_retries + 1):
        if not pending:
            break
        outs = chain.batch(
            [rows[i] for i in pending],
            config={"max_concurrency": max_concurrency},
            return_exceptions=True,
        )
        for i, out in zip(pending, outs, strict=True):
            if not isinstance(out, (ReviewAnalysis, Exception)):
                out = TypeError(f"unexpected output type {type(out).__name__}")
            results[i] = out
        # hard failures (invalid values, API errors) and soft failures (reply not in the review's language)
        # are both retried; after the last attempt a soft failure is accepted with its English reply
        pending = [i for i in pending if isinstance(results[i], Exception) or not results[i].reply_language_ok()]
        if pending and attempt < max_retries:
            log.warning("attempt %d: %d review(s) to retry", attempt + 1, len(pending))
    return results


def classify_reviews(
    chain: Runnable,
    rows: list[dict],
    max_concurrency: int,
    max_retries: int,
    on_progress: ProgressFn | None = None,
    chunk_size: int = 25,
) -> list[ReviewAnalysis | Exception]:
    """Classify every row; a row still failing after retries is returned as its Exception."""
    size = max(chunk_size, 1)
    results: list[ReviewAnalysis | Exception] = []
    for start in range(0, len(rows), size):
        results.extend(_run_batch(chain, rows[start : start + size], max_concurrency, max_retries))
        if on_progress:
            on_progress(len(results), len(rows))
    return results
