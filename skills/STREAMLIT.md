# Streamlit Skill

> One-page app: upload → analyse → dashboard → report → export. UI only; logic lives in `reviewlens/`.

---

## Page layout

```
┌ Sidebar ─────────────┐ ┌ Main ─────────────────────────────────────────────┐
│ Model: <LLM_MODEL>   │ │ ReviewLens - Customer Feedback Analyzer           │
│ Max concurrency      │ │ [Upload CSV]  (or) [Use sample data]               │
│ [Analyse reviews]    │ │ Validation summary: 248 rows, 2 dropped (why)      │
│                      │ │ ── after analysis ──                               │
│                      │ │ KPI row: Total | Positive% | Negative% | Urgent    │
│                      │ │ Tabs: Dashboard | Weekly report | Reviews table    │
│                      │ │  Dashboard: sentiment chart, category chart        │
│                      │ │  Report: st.code(report_text) + download .txt      │
│                      │ │  Table: [x] HIGH urgency only, platform filter,    │
│                      │ │         st.dataframe, [Download enriched CSV]      │
└──────────────────────┘ └────────────────────────────────────────────────────┘
```

---

## Session state (no repeat LLM calls)

```python
# app.py
import streamlit as st

st.set_page_config(page_title="ReviewLens", layout="wide")

if "enriched" not in st.session_state:
    st.session_state.enriched = None  # pd.DataFrame after classification
    st.session_state.report = None  # (stats, insights, report_text)
    st.session_state.file_key = None  # name+size of the analysed file

uploaded = st.file_uploader("Upload this week's reviews (CSV)", type="csv")
file_key = f"{uploaded.name}:{uploaded.size}" if uploaded else None
if file_key != st.session_state.file_key:
    st.session_state.enriched = st.session_state.report = None  # new file → reset
```

Run the LLM **only** inside `if st.button("Analyse reviews"):`. Filters, tabs and downloads read from `session_state` and must never call a chain.

---

## Progress

```python
bar = st.progress(0.0, text="Classifying reviews…")


def on_progress(done: int, total: int) -> None:
    bar.progress(done / total, text=f"Classified {done}/{total}")
```

Pass `on_progress` into the classify step, which processes chunks of about 25 rows (see `skills/LANGCHAIN.md`).

---

## Charts (Altair, bundled with Streamlit)

```python
import altair as alt


def bar(counts: dict, title: str) -> alt.Chart:
    data = pd.DataFrame({"label": list(counts), "count": list(counts.values())})
    return (
        alt.Chart(data, title=title)
        .mark_bar()
        .encode(
            x=alt.X("label:N", sort=None, title=None),
            y=alt.Y("count:Q", title="Reviews"),
            tooltip=["label", "count"],
        )
    )


st.altair_chart(bar(stats["sentiment_counts"], "Sentiment"), use_container_width=True)
```

- Fixed sentiment colours: positive green, neutral grey, negative red (`alt.Scale(domain=SENTIMENTS, range=[...])`).
- Feed charts from `compute_stats`, never from LLM output.

---

## Filters + export

```python
high_only = st.toggle("Show only HIGH urgency")
view = df[df.urgency == "high"] if high_only else df
st.dataframe(view, use_container_width=True, hide_index=True)
st.download_button(
    "Download enriched CSV", to_excel_csv(df), file_name=f"reviewlens_enriched_{date.today()}.csv", mime="text/csv"
)
```

Export the **full** enriched table, not the filtered view, unless the label says otherwise. Show `needs_review` rows with a warning badge or count.

---

## Errors

- `InvalidCSVError` → `st.error(str(e))` and `st.stop()`. No LLM calls.
- Missing API key / bad `LLM_MODEL` → catch at `get_llm()` and show a friendly message pointing to `.env.example`.
- Never show raw tracebacks to the manager. Log them instead.

---

## Run

```bash
streamlit run app.py
```
