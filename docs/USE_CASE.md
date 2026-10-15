# Use Case 01 - ReviewLens: Customer Feedback Analyzer

> Source brief, transcribed verbatim in substance. This is the **source of truth** for scope.
> `INITIAL.md`, `CLAUDE.md` and every PRP must trace back to this file.

| Track | Framework | Level | Build time | Interface | Core skill |
|-------|-----------|-------|------------|-----------|------------|
| 1 - Gen AI | LangChain | Intermediate | 2 to 3 days | Streamlit web app | Structured LLM output |

**Goal:** Turn hundreds of raw customer reviews into tagged, prioritised insights and a weekly report a manager can act on in five minutes.

**What you get at the end:** Every review tagged + a weekly insights report.

> Gen AI (LangChain): *you design the steps, the LLM does each step.* Fixed pipeline - no autonomous agents.

---

## 1.1 The real problem

A restaurant chain or online store receives **200 to 500 reviews every week** from Google, Zomato, Swiggy and Amazon. Reviews come in English, Tamil and Tanglish. Today a manager reads them by hand. Urgent complaints (food poisoning, wrong order, rude staff) get missed for days, and nobody can say with numbers *what customers complain about most*.

**Who uses it:** operations manager, customer support team, business owner.

## 1.2 What you will build

- **Upload** a CSV of reviews (columns: `review_id, date, platform, rating, review_text`).
- **Analyse every review** with a LangChain chain that returns a fixed structure: sentiment, category, urgency, a one-line summary and a polite suggested reply.
- **Handle mixed language**: Tamil and Tanglish reviews are understood and summarised in English.
- **Weekly insights report**: a second chain reads all results and writes top complaints, top praises and 3 action items.
- **Dashboard**: sentiment split, category chart, and a filter that shows only HIGH urgency reviews.
- **Export** the enriched table as CSV so the support team can work from it in Excel.

## 1.3 How it works

| # | Step | What happens |
|---|------|--------------|
| 01 | Upload CSV | User uploads the week's reviews |
| 02 | Validate | Check columns, drop empty rows |
| 03 | Classify | Chain tags each review in batches |
| 04 | Aggregate | Count by sentiment, category, urgency |
| 05 | Report | Summary chain writes weekly insights |
| 06 | Show + Export | Dashboard and CSV download |

If the LLM returns an invalid value (for example a category not in the allowed list), the chain retries that review automatically before marking it as `needs review`.

## 1.4 Tech stack and key concepts

| Part | Use | What you learn |
|------|-----|----------------|
| LangChain | `ChatPromptTemplate`, LCEL (`\|`) chains | Building clean, reusable prompt pipelines |
| Structured output | Pydantic model + `with_structured_output()` | Forcing the LLM to return valid, typed JSON every time |
| Batching | `chain.batch()` with `max_concurrency` | Processing hundreds of items fast and within rate limits |
| Map then reduce | Per-review chain, then one report chain | Summarising large data that does not fit in one prompt |
| LLM | OpenAI / Gemini / Claude (any one) | Swapping models without changing the chain |
| UI | Streamlit + pandas + a chart library | Turning AI output into a usable tool |

## 1.5 Sample input - `reviews_week40.csv`

```csv
review_id,date,platform,rating,review_text
R-1041,2026-10-03,Zomato,5,"Biryani was amazing, packing also neat. Will order again!"
R-1042,2026-10-03,Swiggy,1,"Ordered at 8pm, came at 9:10. Food fully cold. Very bad."
R-1043,2026-10-04,Google,2,"Saapadu nalla irundhuchu but bill la extra charge pottanga"
```

## 1.6 Sample output

**Output A - one analysed review (JSON)**

```json
{
  "review_id": "R-1042",
  "sentiment": "negative",
  "category": "delivery",
  "urgency": "high",
  "language": "English",
  "summary": "Order arrived 70 minutes late and the food was cold.",
  "suggested_reply": "We are really sorry your order reached late and cold. We have shared this with our delivery partner. Please DM us your order ID so we can make it right."
}
```

**Output B - weekly insights report**

```text
WEEKLY FEEDBACK REPORT  |  29 Sep to 5 Oct 2026
Total reviews: 248   Positive 61%   Neutral 14%   Negative 25%

TOP 3 COMPLAINTS
  1. Late delivery ............ 34 reviews  (mostly Swiggy, 8pm to 10pm)
  2. Extra charges on bill .... 12 reviews  (Google, Tanglish reviews)
  3. Small portion size ....... 9 reviews

TOP PRAISE
  Biryani taste (41 mentions), neat packaging (18 mentions)

URGENT: 9 reviews need a reply within 24 hours

ACTION ITEMS
  1. Add one extra delivery rider for the 8pm to 10pm slot.
  2. Show packing and service charges clearly on the menu.
  3. Reply to all 9 urgent reviews today using the suggested replies.
```

## 1.7 Output explained

| Output field | What it means | Why it matters |
|--------------|---------------|----------------|
| sentiment | positive, neutral or negative | Shows overall customer mood at a glance |
| category | One of: food_quality, delivery, price, staff, packaging, app | Tells the manager which department to fix |
| urgency | low, medium or high | High = reply today (health, refund, abuse, wrong order) |
| summary | One English sentence, even for Tamil or Tanglish reviews | Manager reads 248 lines instead of 248 paragraphs |
| suggested_reply | Polite, ready-to-post response | Support team just reviews and posts it |
| Weekly report | Counts + top issues + action items | A 5-minute read that turns feedback into decisions |

## 1.8 Done checklist

- [ ] Processes a 200+ row CSV without crashing or timing out.
- [ ] Every review has all 6 fields, and every value is from the allowed list.
- [ ] Tamil and Tanglish reviews get a correct English summary.
- [ ] Report numbers (counts, percentages) exactly match the table, because they are calculated in pandas, not guessed by the LLM.
- [ ] HIGH urgency filter works and the enriched CSV opens correctly in Excel.
- [ ] API key is loaded from a `.env` file and never hard-coded.

**Stretch goals:** Compare this week with last week (trend arrows) | Generate replies in the same language as the review | Email the weekly report automatically every Monday.
