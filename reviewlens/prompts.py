"""All prompt templates."""

from langchain_core.prompts import ChatPromptTemplate

from reviewlens.schemas import CATEGORIES

_CATEGORY_GUIDE = (
    "food_quality = taste, freshness, hygiene or quantity of the food itself; "
    "delivery = late, cold on arrival, missing or wrong items, rider behaviour; "
    "price = bill, extra charges, value for money, offers; "
    "staff = politeness and service of restaurant or support staff; "
    "packaging = spills, containers, neatness; "
    "app = ordering app, payment or order tracking problems."
)

CLASSIFY_SYSTEM = (
    "You analyse customer reviews for an Indian restaurant chain / online store. "
    "Reviews may be in English, Tamil (Tamil script) or Tanglish (Tamil written in Latin letters, "
    "often mixed with English).\n"
    "Rules:\n"
    f"- category: exactly one of {', '.join(CATEGORIES)}. Pick the department that must act. {_CATEGORY_GUIDE}\n"
    "- urgency: high for food safety or health issues, refund demands, abusive or rude staff, or wrong orders; "
    "medium for other clear complaints; low for praise or minor remarks.\n"
    "- summary: exactly one sentence, always in English, faithful to the review.\n"
    "- suggested_reply: short, polite, ready to post, in English; apologise for complaints, thank for praise; "
    "never invent facts and never use placeholders."
)

_FEW_SHOT = [
    (
        "Platform: Swiggy\nRating: 1/5\nReview: Ordered at 8pm, came at 9:10. Food fully cold. Very bad.",
        '{"sentiment": "negative", "category": "delivery", "urgency": "high", "language": "English", '
        '"summary": "Order arrived 70 minutes late and the food was cold.", '
        '"suggested_reply": "We are really sorry your order reached late and cold. We have shared this with our '
        'delivery partner. Please DM us your order ID so we can make it right."}',
    ),
    (
        "Platform: Google\nRating: 2/5\nReview: Saapadu nalla irundhuchu but bill la extra charge pottanga",
        '{"sentiment": "negative", "category": "price", "urgency": "medium", "language": "Tanglish", '
        '"summary": "The food was good but the customer was charged extra on the bill.", '
        '"suggested_reply": "Thank you for your kind words about the food. We are sorry about the confusion on '
        'the bill; please share your bill details so we can review the charges."}',
    ),
    (
        "Platform: Zomato\nRating: 5/5\nReview: பிரியாணி மிகவும் சுவையாக இருந்தது, மீண்டும் ஆர்டர் செய்வேன்!",
        '{"sentiment": "positive", "category": "food_quality", "urgency": "low", "language": "Tamil", '
        '"summary": "The biryani was very tasty and the customer will order again.", '
        '"suggested_reply": "Thank you so much! We are delighted you enjoyed the biryani and look forward to '
        'serving you again."}',
    ),
]

_HUMAN = "Platform: {platform}\nRating: {rating}/5\nReview: {review_text}"


def _escape(text: str) -> str:
    return text.replace("{", "{{").replace("}", "}}")


CLASSIFY_PROMPT = ChatPromptTemplate.from_messages(
    [("system", CLASSIFY_SYSTEM)]
    + [m for q, a in _FEW_SHOT for m in (("human", _escape(q)), ("ai", _escape(a)))]
    + [("human", _HUMAN)]
)

REPORT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an operations analyst writing the weekly customer feedback insights for a manager.\n"
            "From the analysed reviews, identify:\n"
            "- top_complaints: up to 3 complaint themes, most common first. Themes must be specific and "
            "finer-grained than the category (e.g. 'Late delivery', 'Extra charges on bill', 'Small portion size').\n"
            "- top_praise: up to 3 praise themes, most common first.\n"
            "For every theme list ALL review_ids that support it, copied exactly from the input. "
            "In 'note' give a short qualitative pattern (platform, time of day, language) or an empty string.\n"
            "- action_items: exactly 3 concrete, practical actions the manager can take this week.\n"
            "Never write counts or percentages anywhere; numbers are computed separately.",
        ),
        (
            "human",
            "Week statistics (authoritative, for context only):\n{stats}\n\n"
            "Analysed reviews (id | date | platform | rating | sentiment | category | urgency | language | summary):\n"
            "{lines}",
        ),
    ]
)
