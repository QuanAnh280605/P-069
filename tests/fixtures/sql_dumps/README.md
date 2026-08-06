# SQL dump fixture provenance

These fixtures are schema-only inputs for Import SQL Dump P1. They contain
synthetic names and defaults only, with no production credentials or row data.

## PostgreSQL golden fixture

- File: `postgresql_schema.sql`
- Source DDL: `source/postgresql_fixture_source.sql`
- Container image: `postgres:16-alpine`
- Server and tool version: PostgreSQL / `pg_dump` 16.14
- Generated: 2026-08-04
- Command:

  ```bash
  docker exec p069-pg-fixture pg_dump \
    --schema-only --no-owner --no-privileges --no-comments \
    --dbname=postgres --username=postgres
  ```

The generated random `\restrict`/`\unrestrict` key was replaced with the stable
`fixture_restrict_key`. No DDL, type, default, constraint, or dump envelope
statement was otherwise changed.

Coverage includes two schemas, three tables, quoted identifiers, nullable and
defaulted columns, composite primary/foreign keys, and `ALTER TABLE ONLY`.

## MySQL golden fixture

- File: `mysql_schema.sql`
- Source DDL: `source/mysql_fixture_source.sql`
- Container image: official `mysql:8.0` (image ID `6cd09145362d`)
- Server and tool version: MySQL / `mysqldump` 8.0.46
- Generated: 2026-08-05
- Command:

  ```bash
  docker exec p069-mysql-fixture mysqldump \
    --no-data --no-tablespaces --skip-triggers --set-gtid-purged=OFF \
    --skip-dump-date --user=root --password=fixture_only fixture_catalog
  ```

`--skip-dump-date` removes the changing completion timestamp. No generated DDL,
type, default, constraint, directive, or dump-envelope statement was scrubbed.
MySQL stores the final constraint definition rather than its creation history,
so the source `ALTER TABLE` appears as an inline foreign key in the real dump.
The source corpus remains as supplemental compatibility coverage for MySQL
`ALTER TABLE`; the PostgreSQL golden fixture supplies real dump `ALTER` forms.

## Parser compatibility gate

SQLGlot 30.13.0 is pinned in `requirements.txt`. Compatibility tests always use
explicit `read="postgres"` or `read="mysql"` dialects.

| Corpus | Result | Important evidence |
| --- | --- | --- |
| Full PostgreSQL dump envelope | Expected parse error | `\restrict` must be removed by the Phase 3 scanner before AST parsing. |
| PostgreSQL golden core DDL | Pass | Ten `Create`/`Alter` nodes; no generic `Command`; `ALTER TABLE ONLY`, quoted identity and composite FK preserved. |
| MySQL golden core DDL | Pass | Three `Create` nodes; no generic `Command`; backticks, defaults and composite constraints preserved. |
| MySQL supplemental source DDL | Pass | Five core `Create`/`Alter` nodes; no generic `Command`; quoted `ALTER TABLE` preserved. |
| MySQL `timestamp` type | Parse with caveat | SQLGlot normalizes it to `TIMESTAMPTZ`; adapters must retain the safe raw type text alongside canonical type. |
