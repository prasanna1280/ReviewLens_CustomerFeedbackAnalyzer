# Generate PRP Command

You are the **PRP Generator**. Turn the product definition into an implementation blueprint the ORCHESTRATOR can execute.

Input: $ARGUMENTS (defaults to `INITIAL.md`)

## Read first
- `INITIAL.md`, `docs/USE_CASE.md`, `CLAUDE.md`
- `agents/ORCHESTRATOR.md` (phases + frozen contracts)
- All files in `skills/`

Research only where the skills are thin or possibly outdated, for example current LangChain APIs or provider structured-output quirks. Cite the URLs in the PRP.

---

## Output: `PRPs/<product-kebab>-prp.md`

```markdown
# PRP: <Product>

## METADATA
| Product | Version | Created | Complexity | Confidence (1-10) |

## GOAL
<1 paragraph from brief> + "Done = every item of brief §1.8 checked."

## CONTEXT
- Docs/URLs consulted (LangChain structured output, batch, init_chat_model, Streamlit APIs)
- Known gotchas (from skills + research)

## CONTRACTS (Phase 0 - written by ORCHESTRATOR)
- Full code for reviewlens/schemas.py and reviewlens/config.py
- Stub signatures for every public function (copied from ORCHESTRATOR.md)
- requirements.txt (pinned minimums), pyproject.toml (pytest + ruff), .env.example

## TASKS
Per agent, ordered, each with: file, what it does, key pseudocode, validation command.
- CHAIN-AGENT: llm.py, prompts.py (incl. few-shot examples), classify.py, report.py
- DATA-AGENT: loader.py, aggregate.py, export.py, report_render.py, scripts/make_sample.py
- UI-AGENT: app.py sections
- TEST-AGENT: test files mapped to §1.8

## PHASES & GATES
| Phase | Agents (parallel) | Gate commands |
| 0 | ORCHESTRATOR | pip install -r requirements.txt; python -c "import reviewlens.schemas" |
| 1 | CHAIN ∥ DATA | ruff check reviewlens; python scripts/make_sample.py |
| 2 | UI ∥ TEST | pytest -q; ruff check . |
| 3 | ORCHESTRATOR | pytest -m live (if key); manual Streamlit checklist |

## DONE-CHECKLIST TRACE
| Brief §1.8 item | Implemented in | Verified by |

## OUT OF SCOPE
Stretch goals not selected, and anything not in the brief.
```

## Report to user

```
PRP GENERATED: PRPs/<name>-prp.md
Tasks: <n> across 4 agents | Phases: 4 | Confidence: <x>/10
NEXT: /execute-prp PRPs/<name>-prp.md
```
