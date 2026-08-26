"""Regenerate and verify expected query results for one golden domain.

Loads the domain's query cases, executes every ``sql_by_dialect["sqlite"]``
against the in-memory SQLite fixture (schema + seed), and rewrites
``expected_results/query_results.json``. Prints one line per result set so
hand-verification against the workbook notes is easy.

Usage: python scripts/verify_golden_results.py [domain]
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_DIR = ROOT / "eval" / "golden_dataset" / (sys.argv[1] if len(sys.argv) > 1 else "ecommerce")


def main() -> None:
    """Execute every golden sqlite SQL and rewrite the expected results file."""
    cases = json.loads((DOMAIN_DIR / "cases" / "query_cases.json").read_text(encoding="utf-8"))
    source = DOMAIN_DIR / "sources" / "sqlite"
    conn = sqlite3.connect(":memory:")
    conn.executescript((source / "schema.sql").read_text(encoding="utf-8"))
    conn.executescript((source / "seed_data.sql").read_text(encoding="utf-8"))

    results: dict[str, list[dict[str, object]]] = {}
    for item in cases:
        expected = item.get("expected")
        if expected is None:
            continue
        sql = expected["sql_by_dialect"]["sqlite"]
        columns = [column[0] for column in conn.execute(sql).description]
        rows = [dict(zip(columns, row, strict=True)) for row in conn.execute(sql).fetchall()]
        results[item["case_id"]] = rows

    out_path = DOMAIN_DIR / "expected_results" / "query_results.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(results)} result sets -> {out_path}")
    for case_id, rows in results.items():
        rendered = ", ".join(f"{row}" for row in rows) if rows else "(empty)"
        print(f"{case_id}: {rendered}")


if __name__ == "__main__":
    main()
