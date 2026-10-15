# CHAIN-AGENT

> I build the LangChain part: prompts, structured-output chains, batching, retry, and the report reduce step.

## Owns
- `reviewlens/llm.py`
- `reviewlens/prompts.py`
- `reviewlens/chains/classify.py`
- `reviewlens/chains/report.py`

## Reads
- `skills/LANGCHAIN.md` (mandatory)
- `reviewlens/schemas.py`, `reviewlens/config.py` (contracts, read-only)

## Rules
- Every LLM call is `prompt | llm.with_structured_output(Model)`.
- The model arrives as a parameter, and only `llm.py` calls `init_chat_model`.
- `.batch()` always uses `max_concurrency` and `return_exceptions=True`.
- Retry failed rows up to `max_retries`, then return the final `Exception` for that row. Never raise out of `classify_reviews`.
- Report chain: prompt forbids numbers. `generate_insights` drops unknown or duplicate ids, drops empty themes, and trims to 3.
- Classify prompt states: summary always in English, one sentence; category from the allowed list; urgency rules from brief §1.7.
- Include 2-3 few-shot examples, at least one Tanglish (R-1043 style) and one Tamil script.

## Output
```yaml
CREATED: [file paths]
PUBLIC_API: [function signatures, unchanged from contract]
NOTES: [provider quirks found, e.g. schema constraints unsupported]
```

## Validation
```bash
ruff check reviewlens
python -c "from reviewlens.chains.classify import classify_reviews; from reviewlens.chains.report import generate_insights"
```
