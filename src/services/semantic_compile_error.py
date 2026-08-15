"""Typed failures exposed by deterministic semantic compilation."""

from __future__ import annotations

from typing import Any


class SemanticCompileError(ValueError):
    """Carry a stable code and safe context for one compile failure."""

    def __init__(self, code: str, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.context = context or {}

    def to_detail(self) -> dict[str, Any]:
        """Return a JSON-safe API error body."""
        return {"code": self.code, "message": str(self), "context": self.context}
