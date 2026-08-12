"""Typed metric definition contract shared by generation, persistence, and compilation."""

from __future__ import annotations

from typing import Any, Literal

import sqlglot
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlglot import exp

MetricFunction = Literal["SUM", "COUNT", "COUNT_DISTINCT", "AVG", "MIN", "MAX"]
MetricStatus = Literal["pending_approval", "approved", "needs_review"]
MetricConfidence = Literal["low", "medium", "high"]
FilterOperator = Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "is_null", "is_not_null"]

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


class MetricFormula(BaseModel):
    """Describe a deterministic aggregation over a base-entity expression."""

    function: MetricFunction
    expression: str = Field(..., min_length=1, max_length=1000)

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


class MetricSpec(BaseModel):
    """Canonical business metric persisted in the metadata store."""

    name: str = Field(..., min_length=1, max_length=200)
    formula: MetricFormula
    base_entity: str = Field(..., min_length=1, max_length=200)
    filters: list[MetricFilter] = Field(default_factory=list)
    status: MetricStatus = "pending_approval"
    confidence: MetricConfidence | None = None
    excluded_notes: str = Field(default="", max_length=2000)


class MetricDefinition(BaseModel):
    """Top-level wrapper used by JSON persistence and YAML preview."""

    metric: MetricSpec

    def to_yaml(self) -> str:
        """Render a stable, Unicode YAML preview."""
        payload = self.model_dump(mode="json", exclude_none=True)
        if not payload["metric"]["filters"]:
            payload["metric"].pop("filters")
        return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
