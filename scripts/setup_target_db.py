"""Setup Target Database Script for New Environment.

Pure Python setup tool with ZERO external package requirements.
Works across Windows, Linux, and macOS.

Usage:
    python scripts/setup_target_db.py
"""

import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PG_SCHEMA_PATH = os.path.join(DATA_DIR, "golden_retail_schema_pg.sql")
PG_SEED_PATH = os.path.join(DATA_DIR, "golden_retail_seed_pg.sql")


def run_cmd(cmd: str, input_str: str = None) -> bool:
    """Run shell command cleanly with optional input."""
    try:
        res = subprocess.run(
            cmd,
            input=input_str,
            text=True,
            encoding="utf-8",
            capture_output=True,
            shell=True,
            check=True
        )

        return True, res.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr or e.stdout


def main() -> None:
    print("🚀 Setting up Golden Retail Target Database (36 Tables, 8.5MB Seed Data)...")

    # 0. Ensure schema & seed SQL files exist (auto-generate if missing)
    if not os.path.exists(PG_SCHEMA_PATH) or not os.path.exists(PG_SEED_PATH):
        print("🌱 Seed data SQL file missing. Auto-generating seed data...")
        scripts_dir = os.path.dirname(__file__)
        gen_py = os.path.join(scripts_dir, "seed_data_generator.py")
        conv_py = os.path.join(scripts_dir, "convert_to_postgres.py")
        run_cmd(f'"{sys.executable}" "{gen_py}"')
        run_cmd(f'"{sys.executable}" "{conv_py}"')

    container_name = "p-069-postgres-1"
    
    # 1. Terminate existing sessions to golden_retail_db if any
    run_cmd(f'docker exec {container_name} psql -U dev -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = \'golden_retail_db\' AND pid <> pg_backend_pid();"')

    # 2. Re-create database golden_retail_db
    print("⚙️  Creating database 'golden_retail_db'...")
    run_cmd(f'docker exec {container_name} psql -U dev -d postgres -c "DROP DATABASE IF EXISTS golden_retail_db;"')
    ok, out = run_cmd(f'docker exec {container_name} psql -U dev -d postgres -c "CREATE DATABASE golden_retail_db;"')
    if not ok:
        print(f"❌ Failed to create database: {out}")
        sys.exit(1)
    print("✅ Created database 'golden_retail_db'.")

    # 3. Import Schema
    print("⏳ Importing 36 DDL tables from golden_retail_schema_pg.sql...")
    with open(PG_SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    ok, out = run_cmd(f'docker exec -i {container_name} psql -U dev -d golden_retail_db', input_str=schema_sql)
    if not ok:
        print(f"❌ Failed to import schema: {out}")
        sys.exit(1)
    print("✅ Successfully imported 36 DDL tables!")

    # 4. Import Seed Dataset
    print("⏳ Importing 8.5 MB seed dataset from golden_retail_seed_pg.sql...")
    with open(PG_SEED_PATH, "r", encoding="utf-8") as f:
        seed_sql = f.read()
    ok, out = run_cmd(f'docker exec -i {container_name} psql -U dev -d golden_retail_db', input_str=seed_sql)
    if not ok:
        print(f"❌ Failed to import seed dataset: {out}")
        sys.exit(1)
    print("✅ Successfully imported 8.5 MB seed dataset (5,000 Orders, 1,000 Customers, 8,000 Sessions)!")

    print("\n🎉 Target Database setup completed 100% successfully!")
    print("📌 Connection URL for testing:")
    print("   postgresql://dev:devpassword@postgres:5432/golden_retail_db")


if __name__ == "__main__":
    main()
