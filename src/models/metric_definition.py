"""Typed metric definition contract shared by generation, persistence, and compilation."""

from __future__ import annotations

import logging
from typing import Any, Literal

import sqlglot
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlglot import exp

logger = logging.getLogger(__name__)

MetricFunction = Literal["SUM", "COUNT", "COUNT_DISTINCT", "AVG", "MIN", "MAX"]
MetricStatus = Literal["draft", "pending_approval", "approved", "needs_review", "unverified"]
MetricConfidence = Literal["low", "medium", "high"]
FilterOperator = Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "is_null", "is_not_null"]
ExpressionKind = Literal["column", "literal", "add", "sub", "mul", "div", "neg"]

_ALLOWED_EXPRESSION_NODES = (
    exp.Column,
    exp.Identifier,
    exp.Literal,
    exp.Paren,
    exp.Add,
    exp.Sub,
    exp.Mul,
    exp.Div,
    exp.Neg,
)


class MetricDiagnostic(BaseModel):
    """Describe why a canonical metric requires review."""

    code: str
    message: str


class MetricExpressionNode(BaseModel):
    """Represent one typed node in a resolved arithmetic expression."""

    kind: ExpressionKind
    column_id: int | None = None
    value: float | None = None
    children: list[MetricExpressionNode] = Field(default_factory=list)


class MetricGrain(BaseModel):
    """Identify the canonical columns that uniquely define the base grain."""

    column_ids: list[int] = Field(default_factory=list)


class MetricFormula(BaseModel):
    """Describe a deterministic aggregation over a base-entity expression."""

    function: MetricFunction
    expression: str = Field(..., min_length=1, max_length=1000)
    expression_ast: MetricExpressionNode | None = None

    @field_validator("function", mode="before")
    @classmethod
    def normalize_function(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("expression", mode="before")
    @classmethod
    def normalize_expression(cls, value: Any) -> Any:
        """Trim an expression while preserving invalid qualifications for validation."""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("expression")
    @classmethod
    def validate_expression(cls, value: str) -> str:
        """Reject SQL statements, functions, strings, and qualified identifiers."""
        cleaned = value.strip()
        if cleaned == "*":
            return cleaned
        try:
            parsed = sqlglot.parse_one(cleaned)
        except sqlglot.errors.ParseError as exc:
            raise ValueError("Invalid metric expression") from exc
        for node in parsed.walk():
            if not isinstance(node, _ALLOWED_EXPRESSION_NODES):
                raise ValueError(f"Expression node {type(node).__name__} is not allowed")
            if isinstance(node, exp.Literal) and not node.is_number:
                raise ValueError("Only numeric literals are allowed in metric expressions")
            if isinstance(node, exp.Column) and node.table:
                raise ValueError("Metric expressions cannot reference another entity")
        return cleaned

    @model_validator(mode="after")
    def validate_star(self) -> MetricFormula:
        """Allow star only for COUNT."""
        if self.expression == "*" and self.function != "COUNT":
            raise ValueError("star is only valid with COUNT")
        return self


class MetricFilter(BaseModel):
    """Represent a fixed predicate without embedding SQL."""

    field: str = Field(..., min_length=1, max_length=200, pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$")
    column_id: int | None = None
    operator: FilterOperator
    value: Any = None

    @model_validator(mode="after")
    def validate_value_shape(self) -> MetricFilter:
        """Validate operator-specific value presence and collection shape."""
        if self.operator in {"is_null", "is_not_null"}:
            if self.value is not None:
                raise ValueError(f"{self.operator} does not accept a value")
        elif self.operator in {"in", "not_in"}:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError(f"{self.operator} requires a non-empty list")
        elif self.value is None:
            raise ValueError(f"{self.operator} requires a value")
        return self


_OP_MAP = {
    "=": "eq",
    "==": "eq",
    "eq": "eq",
    "!=": "neq",
    "<>": "neq",
    "neq": "neq",
    ">": "gt",
    "gt": "gt",
    ">=": "gte",
    "gte": "gte",
    "<": "lt",
    "lt": "lt",
    "<=": "lte",
    "lte": "lte",
    "in": "in",
    "not in": "not_in",
    "not_in": "not_in",
    "is null": "is_null",
    "is_null": "is_null",
    "is not null": "is_not_null",
    "is_not_null": "is_not_null",
}


class MetricSpec(BaseModel):
    """Canonical business metric persisted in the metadata store."""

    name: str = Field(..., min_length=1, max_length=200)
    formula: MetricFormula
    base_entity: str = Field(..., min_length=1, max_length=200)
    base_entity_id: int | None = None
    grain: MetricGrain = Field(default_factory=MetricGrain)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[MetricFilter] = Field(default_factory=list)
    status: MetricStatus = "pending_approval"
    confidence: MetricConfidence | None = None
    excluded_notes: str = Field(default="", max_length=2000)
    preferred_join_paths: dict[int, list[int]] = Field(default_factory=dict)

    @field_validator("dimensions", mode="before")
    @classmethod
    def normalize_dimensions(cls, value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            res: list[str] = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    res.append(item.strip())
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("column_name") or item.get("business_name")
                    if name:
                        res.append(str(name).strip())
            return res
        return []

    @field_validator("preferred_join_paths", mode="before")
    @classmethod
    def coerce_preferred_join_paths(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        cleaned: dict[Any, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and not k.isdigit() and not (k.startswith("-") and k[1:].isdigit()):
                continue
            cleaned[k] = v
        return cleaned

    @field_validator("preferred_join_paths")
    @classmethod
    def validate_preferred_join_paths(cls, value: dict[int, list[int]]) -> dict[int, list[int]]:
        """Reject malformed preferred join-path maps before persistence.

        Keys are target entity ids and values are ordered relationship-id paths
        from the metric base entity. Every id must be a positive integer, each
        path must be non-empty, and a path must not repeat a relationship id.
        """
        for target_id, path in value.items():
            if not isinstance(target_id, int) or isinstance(target_id, bool) or target_id <= 0:
                raise ValueError("preferred_join_paths keys must be positive integers")
            if not isinstance(path, list) or not path:
                raise ValueError("preferred_join_paths values must be non-empty lists")
            seen: set[int] = set()
            for rel_id in path:
                if not isinstance(rel_id, int) or isinstance(rel_id, bool) or rel_id <= 0:
                    raise ValueError("preferred_join_paths relationship ids must be positive integers")
                if rel_id in seen:
                    raise ValueError("preferred_join_paths must not repeat a relationship id")
                seen.add(rel_id)
        return value

    @field_validator("filters", mode="before")
    @classmethod
    def normalize_filters(cls, value: Any) -> list[Any]:
        if not value or not isinstance(value, list):
            return []
        valid_filters = []
        for item in value:
            if isinstance(item, MetricFilter):
                valid_filters.append(item)
            elif isinstance(item, dict):
                fld = item.get("field") or item.get("column") or item.get("name")
                raw_op = str(item.get("operator", "eq")).strip().lower()
                op = _OP_MAP.get(raw_op)
                val = item.get("value")
                if fld and op:
                    valid_filters.append(
                        {
                            "field": str(fld).strip(),
                            "column_id": item.get("column_id"),
                            "operator": op,
                            "value": val,
                        }
                    )
        return valid_filters

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: Any) -> str:
        cleaned = value.strip().lower() if isinstance(value, str) else ""
        if cleaned in {"draft", "pending_approval", "approved", "needs_review", "unverified"}:
            return cleaned
        return "pending_approval"

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: Any) -> str | None:
        if isinstance(value, str) and value.strip().lower() in {"low", "medium", "high"}:
            return value.strip().lower()
        return "high"


class MetricDefinition(BaseModel):
    """Top-level wrapper used by JSON persistence and YAML preview."""

    schema_version: Literal[1, 2] = 1
    metric: MetricSpec
    diagnostics: list[MetricDiagnostic] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_metric_payload(cls, data: Any) -> Any:
        """Wrap flat metric specification in a 'metric' container if needed."""
        if isinstance(data, dict):
            if "metric" in data and isinstance(data["metric"], dict):
                return data
            if "name" in data or "formula" in data or "base_entity" in data:
                return {"metric": data}
        return data

    def to_yaml(self) -> str:
        """Render a stable, Unicode YAML preview."""
        payload = self.model_dump(mode="json", exclude_none=True)
        if not payload["metric"].get("filters"):
            payload["metric"].pop("filters", None)
        if not payload["metric"].get("preferred_join_paths"):
            payload["metric"].pop("preferred_join_paths", None)
        if not payload["metric"].get("dimensions"):
            payload["metric"].pop("dimensions", None)
        return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
