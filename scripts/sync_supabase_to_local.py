"""Synchronize data from Supabase PostgreSQL to Local/VPS PostgreSQL.

Uses IPv4 Supavisor Pooler to avoid IPv6 unreachable errors and bypasses pg_dump version mismatch.
"""

import asyncio
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import asyncpg


# Supabase IPv4 Pooler configuration
DEFAULT_SUPABASE_DSN = os.getenv(
    "SUPABASE_DSN",
    "postgresql://postgres.wyzxcnbnosbhrkehuxuu:Quananh123%4012@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres",
)

# Local/Target DB configuration
DEFAULT_LOCAL_DSN = os.getenv(
    "LOCAL_DSN",
    os.getenv("DATABASE_URL", "postgresql://dev:devpassword@localhost:5432/semantic_layer_dev").replace(
        "postgresql+asyncpg://", "postgresql://"
    ),
)

# Ordered tables according to foreign key constraints
TABLE_SYNC_ORDER = [
    "alembic_version",
    "users",
    "user_sessions",
    "semantic_databases",
    "imported_schemas",
    "semantic_tables",
    "semantic_columns",
    "canonical_relationships",
    "live_target_databases",
    "semantic_metrics",
    "metric_versions",
]


async def sync_table(src_conn: asyncpg.Connection, dest_conn: asyncpg.Connection, table_name: str) -> int:
    """Sync all rows of a table from source to destination."""
    # Check if table exists on source
    table_exists = await src_conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = $1
        )
    """,
        table_name,
    )
    if not table_exists:
        print(f"  ⏭️ Table '{table_name}' does not exist on source, skipping.")
        return 0

    # Fetch column definitions
    columns_info = await src_conn.fetch(
        """
        SELECT column_name, data_type, udt_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
    """,
        table_name,
    )
    col_names = [c["column_name"] for c in columns_info]
    json_cols = {c["column_name"] for c in columns_info if c["data_type"] in ("json", "jsonb")}

    # Read rows from source
    quoted_cols = ", ".join(f'"{c}"' for c in col_names)
    rows = await src_conn.fetch(f'SELECT {quoted_cols} FROM "{table_name}"')
    if not rows:
        print(f"  ℹ️ Table '{table_name}' is empty (0 rows).")
        return 0

    # Disable triggers / truncate destination table first
    await dest_conn.execute(f'TRUNCATE TABLE "{table_name}" CASCADE;')

    # Prepare values for insertion
    col_placeholders = ", ".join(f"${i+1}" for i in range(len(col_names)))
    insert_sql = f'INSERT INTO "{table_name}" ({quoted_cols}) VALUES ({col_placeholders})'

    records = []
    for r in rows:
        record = []
        for col in col_names:
            val = r[col]
            if col in json_cols and val is not None:
                if isinstance(val, (dict, list)):
                    val = json.dumps(val)
            record.append(val)
        records.append(record)

    await dest_conn.executemany(insert_sql, records)

    # Reset sequence if table has serial/auto-increment id
    try:
        seq_name = await dest_conn.fetchval(f"SELECT pg_get_serial_sequence('\"{table_name}\"', 'id')")
        if seq_name:
            await dest_conn.execute(
                f"""
                SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) FROM "{table_name}"), 1), true);
            """
            )
    except Exception:
        pass

    print(f"  ✅ Synced {len(records)} rows into '{table_name}'.")
    return len(records)


async def main():
    src_dsn = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SUPABASE_DSN
    dest_dsn = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_LOCAL_DSN

    print(f"🚀 Starting Sync from Supabase -> Local/VPS DB")
    print(f"📡 Source: {src_dsn.split('@')[-1]}")
    print(f"🎯 Target: {dest_dsn.split('@')[-1]}")

    try:
        src_conn = await asyncpg.connect(src_dsn)
        dest_conn = await asyncpg.connect(dest_dsn)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    total_rows = 0
    try:
        for table in TABLE_SYNC_ORDER:
            rows = await sync_table(src_conn, dest_conn, table)
            total_rows += rows

        print(f"\n🎉 Sync completed successfully! Total rows imported: {total_rows}")
    finally:
        await src_conn.close()
        await dest_conn.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
