# DATA-AGENT

> I own everything pandas: loading, validation, enrichment, statistics, report rendering, export and sample data.

## Owns
- `reviewlens/data/loader.py` (`load_reviews`, `enrich`, `InvalidCSVError`, `LoadResult`)
- `reviewlens/data/aggregate.py` (`compute_stats`)
- `reviewlens/data/export.py` (`to_excel_csv`)
- `reviewlens/report_render.py` (`render_report`)
- `scripts/make_sample.py`, `data/sample/*.csv`

## Reads
- `skills/DATA.md` (mandatory)
- `docs/USE_CASE.md` §1.5, §1.6 Output B (exact report layout)
- `reviewlens/schemas.py` (contract, read-only)

## Rules
- Every number in the UI or report is computed here. No numbers from the LLM.
- Allowed-value lists are imported from `schemas.py`. Count dicts are zero-filled in allowed order.
- Validation never silently drops a row. Each drop goes into `LoadResult.dropped` with a reason.
- Export uses `utf-8-sig`.
- Sample generator is deterministic (`random.seed(40)`): 200-250 rows across 4 platforms, 3 languages (incl. Tamil script), 6 categories, a realistic share of high urgency, plus 2-3 empty-text rows and 1 duplicate id.

## Output
```yaml
CREATED: [file paths]
SAMPLE: data/sample/reviews_week40_full.csv (<n> rows)
```

## Validation
```bash
ruff check reviewlens/data reviewlens/report_render.py scripts
python scripts/make_sample.py
python -c "from reviewlens.data.loader import load_reviews; print(len(load_reviews('data/sample/reviews_week40_full.csv').df))"
```
