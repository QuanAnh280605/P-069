---
description: Generate a new Alembic migration from current model changes
---

Generate a new Alembic migration for the schema changes described or currently
present in the models.

Run `alembic revision --autogenerate -m "$ARGUMENTS"` using a concise, kebab-case
message derived from $ARGUMENTS. After it runs:

1. Show the path of the generated migration file.
2. Summarize the detected schema changes (both `upgrade` and `downgrade`).
3. Flag any empty migration (no changes detected) so we can investigate.

Remember the AGENTS.md rule: every schema change MUST ship with a new migration;
never edit an already-applied migration.
