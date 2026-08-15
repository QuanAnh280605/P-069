"""State schema definitions for the Query Clarifier Guided Wizard Agent."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field

from src.models.schemas import SemanticQuerySpec


class QueryClarifyOption(BaseModel):
    """Represent a single selectable option in the Guided Wizard."""

    id: str = Field(..., description="Normalized option ID, e.g. 'metric:12' or 'dimension:45'")
    label: str = Field(..., description="Short Vietnamese label for UI radio button or chip")
    description: str = Field(default="", description="Optional additional description")


class WizardStepOutput(BaseModel):
    """Represent one step output generated for the user interface."""

    step: int = Field(..., description="Step index (1: Metric selection, 2: Dimension selection)")
    title: str = Field(..., description="Step header title in Vietnamese")
    question: str = Field(..., description="Guided question in Vietnamese")
    options: list[QueryClarifyOption] = Field(default_factory=list, description="List of radio options")
    is_completed: bool = Field(default=False, description="True if wizard resolution is done")


class QueryClarifierState(TypedDict, total=False):
    """State stored during the Guided Wizard query building workflow."""

    db_id: int
    user_id: int
    catalog_context: dict[str, Any]
    approved_metrics: list[dict[str, Any]]
    current_step: int
    selected_metric_ids: list[int]
    selected_dimension_ids: list[int]
    selected_time_grain: str | None
    selected_option_id: str | None
    wizard_step: WizardStepOutput | None
    resolved_spec: SemanticQuerySpec | None
    error_message: str | None
