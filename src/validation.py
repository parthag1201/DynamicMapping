from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from src.models import ValidationResult
from src.schema_registry import FieldMeta


def _coerce_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "t", "1", "yes", "y"}:
            return True
        if lowered in {"false", "f", "0", "no", "n"}:
            return False
    raise ValueError("Invalid boolean value")


def _coerce_number(value: Any) -> float:
    try:
        return float(Decimal(str(value).strip()))
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid numeric value")


def _coerce_date(value: Any) -> str:
    if isinstance(value, str):
        value = value.strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
    raise ValueError("Invalid date value")


def _coerce_field(meta: FieldMeta, value: Any) -> Any:
    if value is None:
        return None

    if meta.field_type == "boolean":
        return _coerce_boolean(value)

    if meta.field_type == "number":
        return _coerce_number(value)

    text = str(value)
    if meta.format_type == "date":
        return _coerce_date(text)

    if meta.max_length is not None and len(text) > meta.max_length:
        return text[: meta.max_length]

    return text


def coerce_payload(payload: dict[str, Any], registry: dict[str, FieldMeta]) -> tuple[dict[str, Any], list[str]]:
    coerced: dict[str, Any] = {}
    errors: list[str] = []

    for key, value in payload.items():
        meta = registry.get(key)
        if not meta:
            continue
        try:
            coerced[key] = _coerce_field(meta, value)
        except ValueError as exc:
            errors.append(f"{key}: {exc}")

    return coerced, errors


def validate_payload(
    payload: dict[str, Any],
    registry: dict[str, FieldMeta],
    required_fields: list[str],
) -> ValidationResult:
    errors: list[str] = []

    for field in required_fields:
        if field not in payload or payload[field] in (None, ""):
            errors.append(f"Missing required field: {field}")

    for key, value in payload.items():
        meta = registry.get(key)
        if not meta:
            continue
        if meta.enum_values and str(value) not in meta.enum_values:
            errors.append(
                f"{key}: value '{value}' not in enum {meta.enum_values}"
            )

    return ValidationResult(valid=not errors, errors=errors)
