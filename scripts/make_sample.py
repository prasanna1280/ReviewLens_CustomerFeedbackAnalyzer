"""Generate deterministic multi-week sample CSVs in English, Tanglish and Tamil.

Story across the weeks (so trend arrows have something to show):
  W38  baseline - extra-charge complaints are the top issue
  W39  evening delivery delays start rising, charges still a problem
  W40  late delivery peaks (matches the brief's sample report); charges improve after menu update
  W41  extra rider added -> delivery recovers; new containers leak -> packaging complaints spike

Usage: python scripts/make_sample.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"
PLATFORMS = ["Google", "Zomato", "Swiggy", "Amazon"]
DELIVERY_PLATFORMS = ["Swiggy", "Zomato", "Swiggy", "Amazon"]

# theme -> (rating range, delivery-platform bias, [texts in English / Tanglish / Tamil])
THEMES: dict[str, tuple[tuple[int, int], bool, list[str]]] = {
    "praise_biryani": (
        (4, 5),
        False,
        [
            "Biryani was amazing, packing also neat. Will order again!",
            "Best chicken biryani in the area, perfectly spiced.",
            "Mutton biryani was soft and flavourful, totally worth it.",
            "Biryani semma taste, packing um super ah irundhuchu!",
            "Chicken biryani vera level, masala correct ah irundhuchu",
            "Indha area la best biryani idhu dhaan, kandippa marupadiyum order pannuven",
            "பிரியாணி மிகவும் சுவையாக இருந்தது, மீண்டும் ஆர்டர் செய்வேன்!",
            "மட்டன் பிரியாணி அருமை, காரம் சரியாக இருந்தது.",
        ],
    ),
    "praise_service": (
        (4, 5),
        False,
        [
            "Staff at the outlet were very friendly and quick.",
            "Food came hot and fresh, delivery boy was polite.",
            "Great value combo meal, worth the price.",
            "Delivery fast ah vandhuchu, saapadu hot ah irundhuchu. Super!",
            "Staff romba friendly, quick ah serve panninanga",
            "உணவு சூடாகவும் சுவையாகவும் இருந்தது. பேக்கிங் அருமை.",
            "ஊழியர்கள் மிகவும் அன்பாக நடந்துகொண்டார்கள்.",
        ],
    ),
    "praise_packaging": (
        (4, 5),
        False,
        [
            "Packaging was leak proof and very neat, loved it.",
            "Packing neat ah irundhuchu, onnum spill aagala",
            "பேக்கிங் மிகவும் நேர்த்தியாக இருந்தது.",
        ],
    ),
    "neutral": (
        (3, 3),
        False,
        [
            "Food was okay, nothing special. Delivery on time.",
            "Taste average, quantity fine. Might try again.",
            "Saapadu ok dhaan, periya special onnum illa",
            "Parotta ok, salna konjam better ah irundhirukalaam",
            "உணவு சராசரியாக இருந்தது, பரவாயில்லை.",
        ],
    ),
    "late_delivery": (
        (1, 2),
        True,
        [
            "Ordered at 8pm, came at 9:10. Food fully cold. Very bad.",
            "Delivery took more than an hour, food was cold by the time it came.",
            "Late delivery again on a Friday night, 75 minutes wait.",
            "Order placed at 8:30, reached after 10pm. Unacceptable.",
            "Order romba late ah vandhuchu, saapadu ellam aaridichu",
            "8 mani ku order panninen, 9:30 ku dhaan vandhuchu. Romba mosam",
            "டெலிவரி மிகவும் தாமதமாக வந்தது, உணவு குளிர்ந்துவிட்டது.",
            "ஒரு மணி நேரம் காத்திருந்தேன், உணவு ஆறிப்போய் வந்தது.",
        ],
    ),
    "wrong_order": (
        (1, 1),
        True,
        [
            "Wrong order delivered! I ordered veg biryani and got chicken. I am vegetarian.",
            "Two items missing from my order and no response from support.",
            "Veg order kuduthen, non-veg vandhuchu. Refund venum",
            "தவறான ஆர்டர் வந்தது, பணத்தை திருப்பித் தாருங்கள்.",
        ],
    ),
    "extra_charges": (
        (2, 3),
        False,
        [
            "Extra packing charge and service charge added without telling. Not fair.",
            "Bill had hidden charges that were not on the menu.",
            "Saapadu nalla irundhuchu but bill la extra charge pottanga",
            "Bill la GST thavira extra charges irukku, menu la podala",
            "பில்லில் கூடுதல் கட்டணம் சேர்த்திருந்தார்கள், மெனுவில் இல்லை.",
        ],
    ),
    "portion": (
        (2, 2),
        False,
        [
            "Portion size was very small for 250 rupees.",
            "Too expensive for the quantity given.",
            "Chicken konjam kammi ah irundhuchu, quantity romba kammi",
            "அளவு மிகவும் குறைவாக இருந்தது, விலைக்கு ஏற்றதாக இல்லை.",
        ],
    ),
    "food_safety": (
        (1, 1),
        False,
        [
            "Got food poisoning after eating the chicken fried rice. Whole family sick. Need refund.",
            "Found a hair in the curry. Disgusting, want my money back.",
            "Saapitta apram vomiting aachu, food fresh ah illa",
            "உணவில் முடி இருந்தது, மிகவும் அருவருப்பாக இருந்தது.",
        ],
    ),
    "taste_issue": (
        (2, 2),
        False,
        [
            "Biryani was too oily and salty today.",
            "Rice was undercooked and the gravy was bland.",
            "Biryani la uppu romba jaasthi, saapida mudiyala",
        ],
    ),
    "rude_staff": (
        (1, 2),
        False,
        [
            "Staff was very rude when I asked for extra raita.",
            "Manager shouted at us at the counter. Never coming back.",
            "Counter staff romba rude ah pesinanga",
            "கடை ஊழியர் மரியாதை இல்லாமல் பேசினார்.",
        ],
    ),
    "leaking_packaging": (
        (1, 2),
        True,
        [
            "Gravy spilled all over the bag, poor packaging.",
            "Container lid was broken, sambar leaked everywhere.",
            "New containers are flimsy, curry leaked through the bag.",
            "Packing sariyilla, gravy ellam bag la kotti irundhuchu",
            "குழம்பு கசிந்து பை முழுவதும் கொட்டியிருந்தது.",
        ],
    ),
    "app_issue": (
        (1, 3),
        True,
        [
            "Payment deducted twice in the app but order shows failed. Need refund.",
            "Order tracking in the app never updates.",
            "App la payment fail aachu but amount cut aagiduchu",
        ],
    ),
}

# week -> (start Monday, n valid rows, id start, theme weights)
WEEKS: dict[int, tuple[date, int, int, dict[str, int]]] = {
    38: (
        date(2026, 9, 14),
        210,
        800,
        {
            "praise_biryani": 22,
            "praise_service": 14,
            "praise_packaging": 8,
            "neutral": 10,
            "late_delivery": 8,
            "wrong_order": 3,
            "extra_charges": 15,
            "portion": 8,
            "food_safety": 2,
            "taste_issue": 4,
            "rude_staff": 3,
            "leaking_packaging": 3,
            "app_issue": 3,
        },
    ),
    39: (
        date(2026, 9, 21),
        225,
        950,
        {
            "praise_biryani": 20,
            "praise_service": 11,
            "praise_packaging": 8,
            "neutral": 10,
            "late_delivery": 15,
            "wrong_order": 4,
            "extra_charges": 13,
            "portion": 8,
            "food_safety": 2,
            "taste_issue": 4,
            "rude_staff": 3,
            "leaking_packaging": 3,
            "app_issue": 3,
        },
    ),
    40: (
        date(2026, 9, 28),
        230,
        1100,
        {
            "praise_biryani": 18,
            "praise_service": 9,
            "praise_packaging": 7,
            "neutral": 9,
            "late_delivery": 22,
            "wrong_order": 5,
            "extra_charges": 8,
            "portion": 8,
            "food_safety": 2,
            "taste_issue": 4,
            "rude_staff": 3,
            "leaking_packaging": 4,
            "app_issue": 3,
        },
    ),
    41: (
        date(2026, 10, 5),
        240,
        1500,
        {
            "praise_biryani": 22,
            "praise_service": 15,
            "praise_packaging": 3,
            "neutral": 10,
            "late_delivery": 7,
            "wrong_order": 2,
            "extra_charges": 5,
            "portion": 7,
            "food_safety": 1,
            "taste_issue": 3,
            "rude_staff": 2,
            "leaking_packaging": 16,
            "app_issue": 3,
        },
    ),
}


def make_week(week: int) -> list[dict]:
    start, n, id_start, weights = WEEKS[week]
    rng = random.Random(week)
    themes = list(weights)
    rows = []
    for i in range(n):
        theme = rng.choices(themes, weights=[weights[t] for t in themes])[0]
        (lo, hi), delivery_bias, texts = THEMES[theme]
        rows.append(
            {
                "review_id": f"R-{id_start + i}",
                "date": (start + timedelta(days=rng.randint(0, 6))).isoformat(),
                "platform": rng.choice(DELIVERY_PLATFORMS if delivery_bias else PLATFORMS),
                "rating": rng.randint(lo, hi),
                "review_text": rng.choice(texts),
            }
        )
    # validation edge cases: two empty texts and one duplicate id
    rows.append({**rows[1], "review_id": f"R-{id_start + n}", "review_text": ""})
    rows.append({**rows[2], "review_id": f"R-{id_start + n + 1}", "review_text": "  "})
    rows.append({**rows[0], "review_text": "Duplicate id row - should be dropped"})
    rows.sort(key=lambda r: r["date"])
    return rows


def write(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["review_id", "date", "platform", "rating", "review_text"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {path.relative_to(OUT_DIR.parent.parent)}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for week in WEEKS:
        name = "reviews_week40_full.csv" if week == 40 else f"reviews_week{week}.csv"
        write(make_week(week), OUT_DIR / name)


if __name__ == "__main__":
    main()
