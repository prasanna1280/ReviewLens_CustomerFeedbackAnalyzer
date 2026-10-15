"""Pydantic models and the single source of allowed values."""

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

ANALYSIS_FIELDS: tuple[str, ...] = (
    "sentiment",
    "category",
    "urgency",
    "language",
    "summary",
    "reply_english",
    "suggested_reply",
)


class ReviewAnalysis(BaseModel):
    """Structured analysis of one customer review."""

    sentiment: Sentiment
    category: Category = Field(description="The single department most responsible for this review.")
    urgency: Urgency = Field(
        description="high = food safety/health, refund demand, abuse/rude staff or wrong order; "
        "medium = clear complaint needing follow-up; low = praise or minor remark."
    )
    language: Language = Field(
        description="English; Tamil (Tamil script); Tanglish (Tamil in Latin letters, often mixed with English)."
    )
    summary: str = Field(description="ONE sentence in English, even if the review is Tamil or Tanglish.")
    reply_english: str = Field(
        description="The polite, ready-to-post reply written in English. No placeholders like [name]."
    )
    suggested_reply: str = Field(
        description="reply_english rendered in the customer's own language and script: English review -> same "
        "English text; Tamil script review -> Tamil script; Tanglish review -> Tanglish (Tamil words written in "
        "Latin letters, mixed with English the way the customer wrote)."
    )

    def reply_language_ok(self) -> bool:
        """False when a Tamil/Tanglish review got a reply that just repeats the English one."""
        return self.language == "English" or self.suggested_reply.strip() != self.reply_english.strip()


class Theme(BaseModel):
    """A recurring theme backed by review ids."""

    theme: str = Field(description="Short label, e.g. 'Late delivery' or 'Extra charges on bill'.")
    review_ids: list[str] = Field(description="IDs of the reviews that support this theme.")
    note: str = Field(
        description="Short qualitative hint such as 'mostly Swiggy, evening orders'. No numbers. Empty string if none."
    )


class WeeklyInsights(BaseModel):
    """Output of the weekly report (reduce) chain."""

    top_complaints: list[Theme] = Field(description="Up to 3 complaint themes, most frequent first.")
    top_praise: list[Theme] = Field(description="Up to 3 praise themes, most frequent first.")
    action_items: list[str] = Field(description="Exactly 3 concrete action items for the manager.")
