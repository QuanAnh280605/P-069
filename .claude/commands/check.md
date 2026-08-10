---
description: Lint + format + test the project (make check)
---

Run `make check` (runs `ruff check`, `ruff format`, then `pytest tests/`) and
report the results.

- If lint errors are found, fix them.
- If tests fail, investigate and fix the failures — do not claim tests pass
  unless they actually pass.
- Summarize pass/fail counts at the end.
