"""Tests for deterministic Metric schema selection."""

from src.services.metric_schema_selector import select_metric_schema


def _schema() -> dict:
    return {
        "tables": [
            {"table_name": "customers", "business_name": "Khách hàng", "columns": []},
            {
                "table_name": "orders",
                "business_name": "Đơn hàng",
                "columns": [{"column_name": "total_amount", "business_name": "Doanh thu"}],
            },
            {"table_name": "stores", "business_name": "Cửa hàng", "columns": []},
            {"table_name": "products", "business_name": "Sản phẩm", "columns": []},
        ],
        "relationships": [
            {"from_table": "orders", "to_table": "stores"},
            {"from_table": "orders", "to_table": "customers"},
        ],
    }


def test_selector_uses_explicit_target_tables_without_llm() -> None:
    result = select_metric_schema(_schema(), "Tính doanh thu", ["products"])

    assert [table["table_name"] for table in result["tables"]] == ["products"]
    assert result["relationships"] == []


def test_selector_ranks_relevant_tables_and_keeps_reachable_neighbor() -> None:
    result = select_metric_schema(_schema(), "Tạo metric doanh thu đơn hàng", max_tables=1)
    names = [table["table_name"] for table in result["tables"]]

    assert names[0] == "orders"
    assert len(names) <= 2
    assert all(
        relation["from_table"] in names and relation["to_table"] in names for relation in result["relationships"]
    )
