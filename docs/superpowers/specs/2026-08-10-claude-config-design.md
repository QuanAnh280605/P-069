# Design: Effective Claude Configuration for P-069

> **Date:** 2026-08-10
> **Branch:** `feat/setup-claude`
> **Status:** Approved

## Goal

Make Claude Code work effectively in the P-069 (AI Semantic Layer Agent) project:
auto-loaded project context, minimal permission friction, automatic code-style
enforcement, and fast paths for the two most common dev loops.

## Context found

- **No `CLAUDE.md`** exists — only `AGENTS.md`. Claude Code auto-loads `CLAUDE.md`
  each session but does **not** auto-load `AGENTS.md`, so the project's rules
  (schema-metadata-only, Fernet encryption, `get_llm()`, async, ≤30 lines/func,
  mandatory Alembic migrations, mock LLM/DB in tests) never reach Claude automatically.
- **`.claude/settings.json`** contains only the AI-logging hooks (already fully
  working via `scripts/log_hook.py --tool=claude`). No `permissions` block — every
  routine command (`pytest`, `ruff`, `git status`) triggers an approval prompt.
- **AI usage logging is complete** — no work needed.
- **Tooling is well-defined:** `Makefile` (`make test/lint/format/check`),
  `ruff.toml` (py311, 120 cols), `pytest.ini` (async auto), Alembic, Docker Compose dev.

## Design (4 surfaces)

### A. `CLAUDE.md` (new, root, ~35 lines)

Auto-loaded every session. Contains:

1. Two-line project context (AI Semantic Layer Agent; Flow 1 generate + Flow 2
   deterministic query; the Canonical-Model redesign in progress).
2. **Critical guardrails** condensed from `AGENTS.md`.
3. **Run commands**: `make test/lint/format/check`, `alembic upgrade head`,
   docker compose dev.
4. `@AGENTS.md` import — pulls the full rules inline so there is a single source
   of truth (no duplicated rule text that can drift).

### B. Permissions allowlist — `.claude/settings.json`

Add a `permissions.allow` block for safe, repeat commands:

- `Bash(make:*)`, `Bash(pytest:*)`, `Bash(ruff:*)`, `Bash(python -m pytest:*)`, `Bash(uvicorn:*)`
- Read-only git: `Bash(git status)`, `Bash(git log:*)`, `Bash(git diff:*)`, `Bash(git branch:*)`, `Bash(git show:*)`
- `Bash(alembic:*)` (dev schema work needs `revision`/`upgrade` constantly)
- `Bash(docker compose:*)`
- `Bash(python scripts/:*)`

**Intentionally omitted** (stay approval-gated): `git commit`, `git push`, destructive
DB ops, anything touching live Target DB data.

### C. Auto-lint/format hook

New `scripts/format_on_edit.py`, wired as a `PostToolUse` hook with matcher
`Edit|Write|MultiEdit`. Reuses the existing `bash scripts/_pyrun.sh <script>`
convention (stdin passes through via `exec`). On any edited `.py` file it runs
`ruff format` then `ruff check --fix` on just that file, skipping `.venv` /
`node_modules` paths. Coexists with the existing logging hook (different matcher).
Frontend (`eslint`) is intentionally out of scope for now.

**Note:** the hook may reformat a file Claude just wrote; the harness invalidates
its cached view so the next read/edit sees the post-ruff content. This is the
standard auto-format-on-save pattern.

### D. Two slash commands — `.claude/commands/`

- **`/new-migration`** → `alembic revision --autogenerate -m "$ARGUMENTS"`, then
  show the generated file and summarize detected changes. Enforces the
  "always migrate on schema change" rule friction-free.
- **`/check`** → `make check` (lint + format + test), report results, fix failures.

## Files changed

| File | Action |
|------|--------|
| `CLAUDE.md` | new |
| `.claude/settings.json` | edit — add `permissions`; add format `PostToolUse` hook |
| `scripts/format_on_edit.py` | new |
| `.claude/commands/new-migration.md` | new |
| `.claude/commands/check.md` | new |

## Verification

- `python scripts/format_on_edit.py` invoked with a sample PostToolUse JSON payload
  formats a temp `.py` file (manual stdin test).
- `.claude/settings.json` is valid JSON (parse check).
- `ruff check` + `ruff format` clean on the new Python script.
- CLAUDE.md `@AGENTS.md` import resolves to a real file.

## Out of scope

Custom subagents, MCP servers, frontend eslint auto-fix, and a settings.local.json
(pre-existing user-local overrides) — all YAGNI for now.
