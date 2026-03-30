from typing import Any
from pydantic import BaseModel, Field


class MapRequest(BaseModel):
    source_id: str = "default"
    headers: list[str] = Field(default_factory=list)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    user_overrides: dict[str, Any] = Field(default_factory=dict)
    confidence_threshold: float | None = None


class MappingDecision(BaseModel):
    source_header: str
    target_field: str | None = None
    confidence: float = 0.0
    method: str = "heuristic"
    rationale: str = ""
    status: str = "rejected"


class OverrideDecision(BaseModel):
    field: str
    status: str
    reason: str = ""


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class MapResponse(BaseModel):
    api_path: str
    payload: dict[str, Any]
    mapping_decisions: list[MappingDecision]
    rejected_mappings: list[MappingDecision]
    override_decisions: list[OverrideDecision]
    validation: ValidationResult
