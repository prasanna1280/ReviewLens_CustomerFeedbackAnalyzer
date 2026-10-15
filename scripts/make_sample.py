"""Generate data/sample/reviews_week40_full.csv deterministically (230+ rows).

Usage: python scripts/make_sample.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "sample" / "reviews_week40_full.csv"
PLATFORMS = ["Google", "Zomato", "Swiggy", "Amazon"]
WEEK_START = date(2026, 9, 29)

# (text, rating range, weight). Mix of English, Tanglish and Tamil script; positive, neutral, negative.
TEMPLATES: list[tuple[str, tuple[int, int], int]] = [
    # --- praise ---
    ("Biryani was amazing, packing also neat. Will order again!", (5, 5), 8),
    ("Best chicken biryani in the area, perfectly spiced.", (4, 5), 7),
    ("Food came hot and fresh, delivery boy was polite.", (4, 5), 5),
    ("Packaging was leak proof and very neat, loved it.", (4, 5), 5),
    ("Staff at the outlet were very friendly and quick.", (4, 5), 4),
    ("Biryani semma taste, packing um super ah irundhuchu!", (5, 5), 6),
    ("Parotta and salna vera level, will definitely order again", (4, 5), 4),
    ("பிரியாணி மிகவும் சுவையாக இருந்தது, மீண்டும் ஆர்டர் செய்வேன்!", (5, 5), 4),
    ("உணவு சூடாகவும் சுவையாகவும் இருந்தது. பேக்கிங் அருமை.", (4, 5), 3),
    ("Great value combo meal, worth the price.", (4, 5), 3),
    # --- neutral ---
    ("Food was okay, nothing special. Delivery on time.", (3, 3), 6),
    ("Taste average, quantity fine. Might try again.", (3, 3), 4),
    ("Saapadu ok dhaan, periya special onnum illa", (3, 3), 3),
    ("App was a bit slow to load but order went through fine.", (3, 4), 3),
    # --- delivery complaints ---
    ("Ordered at 8pm, came at 9:10. Food fully cold. Very bad.", (1, 2), 8),
    ("Delivery took more than an hour, food was cold by the time it came.", (1, 2), 7),
    ("Late delivery again on a Friday night, 75 minutes wait.", (1, 2), 6),
    ("Order romba late ah vandhuchu, saapadu ellam aaridichu", (1, 2), 5),
    ("Wrong order delivered! I ordered veg biryani and got chicken. I am vegetarian.", (1, 1), 4),
    ("Two items missing from my order and no response from support.", (1, 2), 3),
    ("டெலிவரி மிகவும் தாமதமாக வந்தது, உணவு குளிர்ந்துவிட்டது.", (1, 2), 3),
    # --- price complaints ---
    ("Saapadu nalla irundhuchu but bill la extra charge pottanga", (2, 3), 5),
    ("Extra packing charge and service charge added without telling. Not fair.", (2, 2), 5),
    ("Bill la GST thavira extra charges irukku, menu la podala", (2, 2), 3),
    ("Too expensive for the quantity given.", (2, 3), 4),
    # --- food quality complaints ---
    ("Portion size was very small for 250 rupees.", (2, 2), 5),
    ("Biryani was too oily and salty today.", (2, 2), 4),
    ("Got food poisoning after eating the chicken fried rice. Whole family sick. Need refund.", (1, 1), 3),
    ("Found a hair in the curry. Disgusting, want my money back.", (1, 1), 2),
    ("Chicken konjam kammi ah irundhuchu, quantity romba kammi", (2, 2), 3),
    # --- staff complaints ---
    ("Staff was very rude when I asked for extra raita.", (1, 2), 3),
    ("Manager shouted at us at the counter. Never coming back.", (1, 1), 2),
    ("Counter staff romba rude ah pesinanga", (1, 2), 2),
    # --- packaging ---
    ("Gravy spilled all over the bag, poor packaging.", (2, 2), 4),
    ("Container lid was broken, sambar leaked everywhere.", (1, 2), 3),
    # --- app ---
    ("Payment deducted twice in the app but order shows failed. Need refund.", (1, 1), 3),
    ("Order tracking in the app never updates.", (2, 3), 3),
]


def main() -> None:
    random.seed(40)
    texts = [t for t, _, w in TEMPLATES for _ in range(w)]
    meta = {t: r for t, r, _ in TEMPLATES}
    rows = []
    for n in range(230):
        text = random.choice(texts)
        lo, hi = meta[text]
        rows.append(
            {
                "review_id": f"R-{1100 + n}",
                "date": (WEEK_START + timedelta(days=random.randint(0, 6))).isoformat(),
                "platform": random.choice(PLATFORMS),
                "rating": random.randint(lo, hi),
                "review_text": text,
            }
        )
    # validation edge cases: empty text and a duplicate id
    rows.append({"review_id": "R-1400", "date": "2026-10-04", "platform": "Google", "rating": 3, "review_text": ""})
    rows.append({"review_id": "R-1401", "date": "2026-10-05", "platform": "Zomato", "rating": 4, "review_text": "  "})
    rows.append({**rows[0], "review_text": "Duplicate id row - should be dropped"})
    rows.sort(key=lambda r: r["date"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["review_id", "date", "platform", "rating", "review_text"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
