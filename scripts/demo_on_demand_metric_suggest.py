"""Demo script to execute on_demand_metric_suggest_node and display user-facing Business Metrics."""

from __future__ import annotations

import os

os.environ["LANGCHAIN_TRACING_V2"] = "false"

import asyncio
import json
import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.nodes.on_demand_metric_suggest_node import on_demand_metric_suggest_node

# E-Commerce Canonical Schema Metadata Example
SAMPLE_CANONICAL_SCHEMA = {
    "source": {
        "type": "live_connection",
        "db_engine": "postgresql",
        "connection_id": 101,
        "extracted_at": "2026-08-10T12:00:00Z",
    },
    "tables": [
        {
            "table_name": "orders",
            "business_name": "Đơn hàng",
            "schema_name": "public",
            "primary_keys": ["id"],
            "foreign_keys": [
                {
                    "constrained_columns": ["customer_id"],
                    "referred_table": "customers",
                    "referred_columns": ["id"],
                }
            ],
            "columns": [
                {"column_name": "id", "data_type": "INTEGER", "is_primary_key": True, "is_foreign_key": False, "is_nullable": False},
                {"column_name": "customer_id", "data_type": "INTEGER", "is_primary_key": False, "is_foreign_key": True, "is_nullable": False},
                {"column_name": "total_amount", "data_type": "NUMERIC(15,2)", "business_name": "Tổng tiền", "is_primary_key": False, "is_foreign_key": False, "is_nullable": False},
                {"column_name": "status", "data_type": "VARCHAR(20)", "business_name": "Trạng thái", "is_primary_key": False, "is_foreign_key": False, "is_nullable": False},
                {"column_name": "order_date", "data_type": "TIMESTAMP", "business_name": "Ngày đặt", "is_primary_key": False, "is_foreign_key": False, "is_nullable": False},
                {"column_name": "is_deleted", "data_type": "BOOLEAN", "business_name": "Đã xóa", "is_primary_key": False, "is_foreign_key": False, "is_nullable": False},
            ],
        },
        {
            "table_name": "order_items",
            "business_name": "Chi tiết đơn hàng",
            "schema_name": "public",
            "primary_keys": ["id"],
            "foreign_keys": [
                {"constrained_columns": ["order_id"], "referred_table": "orders", "referred_columns": ["id"]},
                {"constrained_columns": ["product_id"], "referred_table": "products", "referred_columns": ["id"]},
            ],
            "columns": [
                {"column_name": "id", "data_type": "INTEGER", "is_primary_key": True, "is_foreign_key": False, "is_nullable": False},
                {"column_name": "order_id", "data_type": "INTEGER", "is_primary_key": False, "is_foreign_key": True, "is_nullable": False},
                {"column_name": "product_id", "data_type": "INTEGER", "is_primary_key": False, "is_foreign_key": True, "is_nullable": False},
                {"column_name": "quantity", "data_type": "INTEGER", "business_name": "Số lượng", "is_primary_key": False, "is_foreign_key": False, "is_nullable": False},
                {"column_name": "unit_price", "data_type": "NUMERIC(15,2)", "business_name": "Đơn giá", "is_primary_key": False, "is_foreign_key": False, "is_nullable": False},
            ],
        },
        {
            "table_name": "customers",
            "business_name": "Khách hàng",
            "schema_name": "public",
            "primary_keys": ["id"],
            "foreign_keys": [],
            "columns": [
                {"column_name": "id", "data_type": "INTEGER", "is_primary_key": True, "is_foreign_key": False, "is_nullable": False},
                {"column_name": "full_name", "data_type": "VARCHAR(100)", "business_name": "Họ và tên", "is_primary_key": False, "is_foreign_key": False, "is_nullable": False},
                {"column_name": "email", "data_type": "VARCHAR(100)", "business_name": "Email", "is_primary_key": False, "is_foreign_key": False, "is_nullable": False},
                {"column_name": "is_active", "data_type": "BOOLEAN", "business_name": "Đang hoạt động", "is_primary_key": False, "is_foreign_key": False, "is_nullable": False},
            ],
        },
    ],
    "relationships": [
        {"from_table": "orders", "from_column": "customer_id", "to_table": "customers", "to_column": "id", "relationship_type": "many_to_one"},
        {"from_table": "order_items", "from_column": "order_id", "to_table": "orders", "to_column": "id", "relationship_type": "many_to_one"},
    ],
}


async def main() -> None:
    print("=" * 80)
    print(" 🔍 Đang chạy Agent On-demand Metric Generator (on_demand_metric_suggest_node)...")
    print("=" * 80)

    state = {"enriched_schema": SAMPLE_CANONICAL_SCHEMA}
    result = await on_demand_metric_suggest_node(state)

    if "error" in result:
        print(f"\n❌ Lỗi: {result['error']}")
        return

    metrics = result.get("suggested_metrics", [])
    print(f"\n✅ Agent đã sinh thành công {len(metrics)} Business Metrics!\n")

    # Format table for terminal output
    print("-" * 100)
    print(f"{'STT':<4} | {'Tên nghiệp vụ (business_name)':<25} | {'Tên kỹ thuật (name)':<20} | {'Bảng gốc':<12} | {'Phép toán':<10} | {'Cột tính':<15}")
    print("-" * 100)

    for idx, m in enumerate(metrics, 1):
        b_name = m.get("business_name", "")
        name = m.get("name", "")
        tbl = m.get("target_table", "")
        agg = m.get("aggregation", "")
        fld = m.get("field", "")
        print(f"{idx:<4} | {b_name:<25} | {name:<20} | {tbl:<12} | {agg:<10} | {fld:<15}")
        print(f"     Mô tả: {m.get('description', '')}")
        print(f"     SQL Mẫu: {m.get('sql_template', '')}")
        print("-" * 100)

    print("\n📦 Cấu trúc JSON chi tiết nhận được từ Agent:")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
