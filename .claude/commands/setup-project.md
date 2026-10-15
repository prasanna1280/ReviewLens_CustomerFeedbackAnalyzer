# Setup Project Command

You are the **Project Setup Wizard** for a GenAI use-case project. The use case brief already decides most things. Your job is to turn it into `INITIAL.md` and `CLAUDE.md`, asking the user **only** about what the brief leaves open.

Input: $ARGUMENTS (path to the brief; defaults to `docs/USE_CASE.md`)

---

## STEP 1: Read the brief

Read the brief and extract:

```yaml
NAME / GOAL / USERS
TRACK: Gen AI (fixed pipeline) | AI Agents | Agentic AI
INTERFACE: e.g. Streamlit
INPUT: format + columns + volume
PIPELINE: ordered steps (brief "How it works")
OUTPUT_SCHEMA: fields + allowed values (brief "Output explained")
REPORT / AGGREGATES: what is summarised, and which numbers must be computed (not generated)
TECH_STACK: brief "Tech stack and key concepts"
DONE_CHECKLIST: brief "Done checklist" (these become acceptance criteria verbatim)
STRETCH_GOALS
OPEN_CHOICES: anything the brief says "any one" / leaves unspecified
```

If there's no brief, ask the user to paste it (text or screenshots) and save it to `docs/USE_CASE.md` first.

---

## STEP 2: Ask only the open choices

Use AskUserQuestion for items in `OPEN_CHOICES`, for example:

```yaml
- question: "Which LLM provider will you use by default? (Code stays provider-agnostic.)"
  header: "LLM"
  options:
    - label: "OpenAI"        description: "langchain-openai, OPENAI_API_KEY"
    - label: "Google Gemini" description: "langchain-google-genai, GOOGLE_API_KEY"
    - label: "Anthropic Claude" description: "langchain-anthropic, ANTHROPIC_API_KEY"
- question: "Include any stretch goals in this build?"
  header: "Stretch"
  multiSelect: true
  options: [from brief STRETCH_GOALS, plus "None - MVP only (Recommended)"]
```

Don't ask about things the brief doesn't need (auth, database, payments, frontend framework, Docker) unless the brief mentions them. If a choice has a sensible default and the user isn't around, pick the default and record it under "Decisions" in INITIAL.md.

---

## STEP 3: Generate INITIAL.md

Sections, in order:
1. **PRODUCT**: name, type, pattern (fixed pipeline vs agent), users, input, output
2. **TECH STACK**: table; plus an explicit "Not in scope" line for the usual SaaS pieces the brief doesn't need
3. **PIPELINE**: one row per brief step → module path that implements it
4. **DATA CONTRACTS**: input columns; Pydantic output model(s) with allowed values; report model
5. **MVP SCOPE**: done checklist verbatim + supporting deliverables (sample data, README); stretch goals separate
6. **ACCEPTANCE CRITERIA**: testable statements per pipeline step
7. **BUILD ROLES**: agents in `agents/` and the files each owns
8. **NEXT**: `/generate-prp INITIAL.md`

Rules: trace every item to the brief, and don't invent features. Anything numeric in reports must be computed in code (pandas), never by the LLM.

---

## STEP 4: Generate CLAUDE.md

Include: project overview (1 paragraph), folder structure tree, numbered non-negotiable rules (derived from the brief's key concepts and done checklist), code standards, `.env` keys, run/test/lint commands, testing rules (offline fake LLM + opt-in live), skills table, agents line, commit format.

---

## STEP 5: Align the scaffold

- `skills/`: one guide per real technology in the stack. Remove guides for technologies not used.
- `agents/`: one agent per owned code area plus TEST-AGENT, coordinated by `agents/ORCHESTRATOR.md` with a contracts-first Phase 0.
- `.env.example` with every key from CLAUDE.md, empty values.
- `data/sample/` with the brief's sample input.
- Update `README.md` with what the product does and how to run it.

---

## STEP 6: Report

```
SETUP COMPLETE
Brief:     docs/USE_CASE.md
Generated: INITIAL.md, CLAUDE.md, .env.example, data/sample/...
Decisions: <choices made + who made them>
Next:      /generate-prp INITIAL.md
```
