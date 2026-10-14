# ReviewLens - Customer Feedback Analyzer

A GenAI application built with LangChain to analyze customer feedback.

> 🚧 Work in progress. The product definition and setup instructions will be added once the use case is finalized.

## Project workflow

This repo uses the context-engineering workflow with Claude Code:

1. `/setup-project` - generates `INITIAL.md` (product definition) and `CLAUDE.md` (project rules)
2. `/generate-prp INITIAL.md` - generates the implementation plan in `PRPs/`
3. `/execute-prp PRPs/<name>.md` - builds the app using the agents in `agents/` and the guides in `skills/`
