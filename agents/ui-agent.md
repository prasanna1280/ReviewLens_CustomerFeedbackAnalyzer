# UI-AGENT

> I build the Streamlit app. It contains wiring and presentation only.

## Owns
- `app.py`

## Reads
- `skills/STREAMLIT.md` (mandatory)
- Public functions from `reviewlens/` (see the ORCHESTRATOR contract list)

## Rules
- No business logic in `app.py`. Call `load_reviews`, `classify_reviews`, `enrich`, `compute_stats`, `generate_insights`, `render_report` and `to_excel_csv`.
- LLM calls happen only on the "Analyse reviews" button. Results go into `st.session_state` and are reset when a new file is uploaded.
- Must include: upload + "use sample data", validation summary, progress bar, KPI row, sentiment chart, category chart, HIGH-urgency toggle, review table, report panel, CSV download, and a `needs_review` count.
- Friendly errors for a bad CSV and for a missing key or model. No raw tracebacks.

## Output
```yaml
CREATED: [app.py]
SCREENS: [sections implemented]
```

## Validation
```bash
ruff check app.py
python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read())"
streamlit run app.py   # manual smoke with sample data
```
