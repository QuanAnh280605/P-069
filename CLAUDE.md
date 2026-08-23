# CLAUDE.md — P-069: AI Semantic Layer Agent

> The source of truth for AI rules is `AGENTS.md` (imported at the bottom). This
> file adds Claude-specific quick context so every session starts informed.

## Project in 3 lines

AI Agent that builds a **Semantic Layer** for enterprise databases. Two flows:

- **Flow 1 (Generate & Manage):** introspect schema (Live DB / SQL Dump) → LLM
  proposes Vietnamese business names + business metrics → HITL review → save →
  export JSON/YAML.
- **Flow 2 (Query, Live DB only):** deterministic `SemanticQueryCompiler` turns
  approved metrics/dimensions into guarded read-only SQL. **Not** free text-to-SQL.

A **Canonical-Model redesign** (4-stage lifecycle, YAML registry) and an
**Evaluation Framework** are in progress — see `implementation_plan.md` and
`docs/EVALUATION_FRAMEWORK_PLAN.md`.

## Critical guardrails (never violate)

- **Flow 1 = schema metadata only.** Use SQLAlchemy Inspector; **never `SELECT`
  data** on the Target DB. SQL Dump is read-only DDL too.
- **Flow 2 = guarded read-only `SELECT` only** via `SemanticQueryCompiler` +
  `sqlglot`: auto `LIMIT 100` (max 1000), `statement_timeout` 15s. Never
  `INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE`.
- **Connection URLs are Fernet-encrypted**, never plaintext, never logged.
- **Always use `get_llm()`** from `src/services/llm.py` (temp 0.0, Vietnamese
  business names). Never instantiate `ChatOpenAI` directly.
- **Async everywhere**, full type hints, **≤30 lines/function**, ≤500 lines/file.
- **Schema changes require a new Alembic migration** — never edit applied
  migrations or drop/recreate the DB.
- **Tests mock LLM + DB** (SQLite in-memory); never call the real OpenAI API.
- **Never `git commit` or `git push`.** Write and edit code only — the user
  reviews and commits everything themselves.

## Run commands

```bash
make check        # lint (ruff) + format + test (pytest) — run before finishing
make test         # pytest tests/ -v
make lint         # ruff check src/ tests/
make format       # ruff format src/ tests/

uvicorn src.main:app --reload --port 8000        # API server (Swagger at /docs)
alembic upgrade head                            # apply migrations
docker compose -f docker-compose.dev.yml up postgres pgadmin -d # metadata store
```

Custom commands: `/new-migration` (Alembic autogenerate), `/check` (make check).

## Full rules & architecture

@AGENTS.md
