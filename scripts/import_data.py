"""CSV Import Utility Script.

Imports CSV datasets into a target relational database using SQLAlchemy.
Supports command-line arguments and environment variable configuration.
"""

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import Column, MetaData, String, Table, create_engine

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Load environment variables from .env if present
load_dotenv()

DEFAULT_DB_URL = os.getenv("TARGET_DATABASE_URL", "")
DEFAULT_DATA_DIR = os.getenv("CSV_DATA_DIR", "")


def _import_single_csv(csv_path: Path, table_name: str, engine: Any) -> int:
    """Import a single CSV file into database using standard library csv and SQLAlchemy."""
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        if not headers:
            return 0

        metadata = MetaData()
        table = Table(
            table_name,
            metadata,
            *(Column(h, String) for h in headers),
        )

        metadata.drop_all(engine, tables=[table])
        metadata.create_all(engine, tables=[table])

        rows = [dict(zip(headers, row)) for row in reader]
        if rows:
            with engine.begin() as conn:
                conn.execute(table.insert(), rows)
        return len(rows)


def import_csv_files(data_dir: str, db_url: str) -> None:
    """Import all CSV files from data_dir into database specified by db_url."""
    if not data_dir:
        print("❌ Lỗi: Chưa cấu hình CSV_DATA_DIR trong file .env hoặc tham số --dir !")
        sys.exit(1)
    if not db_url:
        print("❌ Lỗi: Chưa cấu hình TARGET_DATABASE_URL trong file .env hoặc tham số --db-url !")
        sys.exit(1)

    path = Path(data_dir)
    if not path.exists() or not path.is_dir():
        print(f"❌ Lỗi: Thư mục '{data_dir}' không tồn tại!")
        sys.exit(1)

    csv_files = sorted(list(path.glob("*.csv")))
    if not csv_files:
        print(f"⚠️  Không tìm thấy file CSV nào trong '{data_dir}'.")
        return

    print(f"📦 Tìm thấy {len(csv_files)} file CSV trong '{data_dir}'...")
    print(f"🔗 Kết nối tới Database: {db_url}\n")

    try:
        engine = create_engine(db_url)
    except Exception as e:
        print(f"❌ Lỗi kết nối Database: {e}")
        sys.exit(1)

    for csv_path in csv_files:
        table_name = csv_path.stem.replace("olist_", "").replace("_dataset", "")
        print(f"⏳ Đang import '{csv_path.name}' vào bảng '{table_name}'...")
        try:
            count = _import_single_csv(csv_path, table_name, engine)
            print(f"✅ Thành công! Đã nạp {count:,} dòng vào bảng '{table_name}'.\n")
        except Exception as e:
            print(f"❌ Lỗi khi import file '{csv_path.name}': {e}\n")

    print("🎉 Hoàn tất import toàn bộ dữ liệu!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CSV datasets into target SQL Database.")
    parser.add_argument(
        "-d",
        "--dir",
        default=DEFAULT_DATA_DIR,
        help="Đường dẫn thư mục chứa file CSV (mặc định lấy từ CSV_DATA_DIR trong .env)",
    )
    parser.add_argument(
        "-u",
        "--db-url",
        default=DEFAULT_DB_URL,
        help="Connection URL của Database (mặc định lấy từ TARGET_DATABASE_URL trong .env)",
    )

    args = parser.parse_args()
    import_csv_files(data_dir=args.dir, db_url=args.db_url)


if __name__ == "__main__":
    main()
