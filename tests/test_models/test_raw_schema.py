"""Tests for RawSchema exposure through response models."""

from src.models.raw_schema import RawSchema
from src.models.schemas import GenerateResponse


def test_generate_response_validates_raw_schema_contract() -> None:
    """Use RawSchema instead of an untyped dictionary in generate responses."""
    raw_schema: RawSchema = {
        "source": {
            "type": "sql_dump",
            "db_engine": "postgresql",
            "connection_id": None,
            "extracted_at": "2026-08-05T00:00:00Z",
        },
        "tables": [],
        "relationships": [],
    }
    response = GenerateResponse(
        db_id=1,
        raw_schema=raw_schema,
        enriched_schema={},
        suggested_metrics=[],
    )
    assert response.raw_schema["source"]["type"] == "sql_dump"
