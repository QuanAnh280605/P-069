"""Convert MySQL Golden Retail Schema and Seed SQL files into PostgreSQL Compatible Syntax.

Outputs:
  - data/golden_retail_schema_pg.sql
  - data/golden_retail_seed_pg.sql
"""

import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

MYSQL_SCHEMA_PATH = os.path.join(DATA_DIR, "golden_retail_schema.sql")
PG_SCHEMA_PATH = os.path.join(DATA_DIR, "golden_retail_schema_pg.sql")

MYSQL_SEED_PATH = os.path.join(DATA_DIR, "golden_retail_seed.sql")
PG_SEED_PATH = os.path.join(DATA_DIR, "golden_retail_seed_pg.sql")


def convert_schema() -> None:
    """Convert MySQL DDL schema to PostgreSQL syntax."""
    with open(MYSQL_SCHEMA_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace AUTO_INCREMENT types with SERIAL
    content = re.sub(r"ID\s+int\(\d+\)\s+NOT\s+NULL\s+AUTO_INCREMENT", "ID SERIAL", content, flags=re.IGNORECASE)
    content = re.sub(r"int\(\d+\)", "INT", content, flags=re.IGNORECASE)
    content = re.sub(r"\bblob\b", "BYTEA", content, flags=re.IGNORECASE)
    content = re.sub(r"binary\(\d+\)", "BYTEA", content, flags=re.IGNORECASE)

    # Remove ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='...'
    content = re.sub(r"\)\s*ENGINE=InnoDB[^\n;]*;", ");", content, flags=re.IGNORECASE)

    with open(PG_SCHEMA_PATH, "w", encoding="utf-8") as f:
        f.write("-- PostgreSQL Compatible Schema for Golden Retail Benchmark\n\n" + content)

    print(f"✅ Converted PostgreSQL schema to: {PG_SCHEMA_PATH}")


def convert_seed() -> None:
    """Convert MySQL DML seed dump to PostgreSQL syntax."""
    with open(MYSQL_SEED_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace MySQL FK disable syntax with Postgres replication role
    content = content.replace("SET FOREIGN_KEY_CHECKS = 0;", "SET session_replication_role = 'replica';")
    content = content.replace("SET FOREIGN_KEY_CHECKS = 1;", "SET session_replication_role = 'origin';")

    with open(PG_SEED_PATH, "w", encoding="utf-8") as f:
        f.write("-- PostgreSQL Compatible Seed Dump for Golden Retail Benchmark\n\n" + content)

    print(f"✅ Converted PostgreSQL seed dump to: {PG_SEED_PATH}")


def main() -> None:
    print("🔄 Converting MySQL schema and seed dump to PostgreSQL...")
    convert_schema()
    convert_seed()
    print("🎉 Conversion completed successfully!")


if __name__ == "__main__":
    main()
