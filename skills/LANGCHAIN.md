# LangChain Skill

> LCEL chains + Pydantic structured output + batching + retry, all provider-agnostic.

---

## Dependencies

```text
langchain>=1.0          # init_chat_model
langchain-core>=1.0
langchain-openai        # install only the provider(s) you use
langchain-google-genai
langchain-anthropic
pydantic>=2
python-dotenv
```

---

## Schemas (single source of allowed values)

```python
# reviewlens/schemas.py
from typing import Literal, get_args
from pydantic import BaseModel, Field

Sentiment = Literal["positive", "neutral", "negative"]
Category = Literal["food_quality", "delivery", "price", "staff", "packaging", "app"]
Urgency = Literal["low", "medium", "high"]
Language = Literal["English", "Tamil", "Tanglish"]

SENTIMENTS: tuple[str, ...] = get_args(Sentiment)
CATEGORIES: tuple[str, ...] = get_args(Category)
URGENCIES: tuple[str, ...] = get_args(Urgency)
LANGUAGES: tuple[str, ...] = get_args(Language)


class ReviewAnalysis(BaseModel):
    """Structured analysis of one customer review."""

    sentiment: Sentiment
    category: Category = Field(description="The single department most responsible.")
    urgency: Urgency = Field(description="high = health/safety, refund, abuse or wrong order.")
    language: Language
    summary: str = Field(description="ONE sentence in English, even if the review is Tamil or Tanglish.")
    suggested_reply: str = Field(description="Polite, ready-to-post reply in English. No placeholders.")


class Theme(BaseModel):
    theme: str = Field(description="Short label, e.g. 'Late delivery'.")
    review_ids: list[str] = Field(description="IDs of reviews that support this theme.")
    note: str = Field(default="", description="Optional qualitative hint, e.g. 'mostly Swiggy, 8pm-10pm'. No numbers.")


class WeeklyInsights(BaseModel):
    top_complaints: list[Theme] = Field(max_length=3)
    top_praise: list[Theme] = Field(max_length=3)
    action_items: list[str] = Field(min_length=3, max_length=3)
```

The `Literal` types do two jobs: the LLM sees them in the JSON schema, and Pydantic rejects anything else. A rejection raises, which triggers our retry.

---

## Model factory (the only provider-aware file)

```python
# reviewlens/llm.py
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from reviewlens.config import settings


def get_llm() -> BaseChatModel:
    """Build the chat model named by LLM_MODEL, e.g. 'openai:<model>' or 'anthropic:<model>'."""
    return init_chat_model(settings.llm_model, temperature=0)
```

---

## Prompts

```python
# reviewlens/prompts.py
from langchain_core.prompts import ChatPromptTemplate
from reviewlens.schemas import CATEGORIES

CLASSIFY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You analyse customer reviews for an Indian restaurant / online store. "
            "Reviews may be English, Tamil (script) or Tanglish (Tamil in Latin letters). "
            "Pick exactly one category from: " + ", ".join(CATEGORIES) + ". "
            "Urgency is high for food safety/health, refund demands, abusive staff, or wrong orders. "
            "Always write the summary in English, as one sentence. "
            "Write a short, polite reply in English that the support team can post as-is.",
        ),
        ("human", "Platform: {platform}\nRating: {rating}/5\nReview: {review_text}"),
    ]
)
```

Few-shot tip: add 2-3 example pairs (including one Tanglish, e.g. brief row R-1043) as extra human/ai messages if language detection or category accuracy is weak.

---

## Map: classify with batch + retry + needs_review

```python
# reviewlens/chains/classify.py
import logging
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from reviewlens.prompts import CLASSIFY_PROMPT
from reviewlens.schemas import ReviewAnalysis

log = logging.getLogger(__name__)


def build_classify_chain(llm: BaseChatModel) -> Runnable:
    return CLASSIFY_PROMPT | llm.with_structured_output(ReviewAnalysis)


def classify_reviews(
    chain: Runnable,
    rows: list[dict],
    max_concurrency: int,
    max_retries: int,
    on_progress=None,
) -> list[ReviewAnalysis | Exception]:
    """Classify every row; failed rows are retried, then left as the final Exception."""
    results: list[ReviewAnalysis | Exception] = [None] * len(rows)  # type: ignore[list-item]
    pending = list(range(len(rows)))
    for attempt in range(max_retries + 1):
        if not pending:
            break
        outs = chain.batch(
            [rows[i] for i in pending],
            config={"max_concurrency": max_concurrency},
            return_exceptions=True,
        )
        for i, out in zip(pending, outs):
            results[i] = out
        pending = [i for i in pending if isinstance(results[i], Exception)]
        if pending:
            log.warning("attempt %d: %d rows failed, retrying", attempt + 1, len(pending))
        if on_progress:
            on_progress(len(rows) - len(pending), len(rows))
    return results
```

The caller turns `Exception` results into `status="needs_review"` with `error=str(exc)[:200]` and empty analysis fields.

For **progress in Streamlit** with 200-500 rows, call `classify_reviews` on chunks of about 25 rows and update `st.progress` between chunks. This keeps concurrency bounded and the UI alive.

**Rate limits:** if the provider returns 429s, lower `MAX_CONCURRENCY`. You can also wrap the model with `llm.with_retry(stop_after_attempt=3, wait_exponential_jitter=True)` *before* `with_structured_output` so transport errors are retried separately from validation errors.

---

## Reduce: weekly insights

```python
# reviewlens/chains/report.py
REPORT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an operations analyst. From the analysed reviews below, find the top complaint themes "
            "and top praise themes (finer-grained than the category, e.g. 'Extra charges on bill'). "
            "For each theme list the review_ids that support it. Do NOT state any counts or percentages. "
            "Then give exactly 3 concrete, actionable items for the manager.",
        ),
        (
            "human",
            "Week stats (authoritative):\n{stats}\n\nReviews (id | platform | sentiment | category | urgency | summary):\n{lines}",
        ),
    ]
)


def build_report_chain(llm):
    return REPORT_PROMPT | llm.with_structured_output(WeeklyInsights)
```

Input `lines` contains one compact line per `ok` review. 500 one-line summaries fit easily in a modern context window, so no extra map step is needed for the MVP.

After the call, **sanitize**: `valid = [i for i in theme.review_ids if i in known_ids]`, de-duplicate, and drop themes left with 0 ids. Counts are `len(valid)`.

---

## Gotchas

- `with_structured_output` returns the Pydantic object directly. Don't add a `StrOutputParser`.
- Prompt variables must match the dict keys you pass to `.batch()` (`platform`, `rating`, `review_text`).
- Curly braces in system text must be doubled `{{ }}` in `ChatPromptTemplate`.
- Gemini and some models reject `max_length` constraints in the schema. If that happens, drop them from the schema and enforce them in Python after the call.
