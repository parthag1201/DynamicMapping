from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CREATE_SCHEMA_NAME = "com.sap.gateway.srvd_a2x.api_plannedorder.v0001.PlannedOrderHeaderType-create"


@dataclass(frozen=True)
class FieldMeta:
    name: str
    title: str
    description: str
    field_type: str
    max_length: int | None
    enum_values: list[str]
    required: bool
    format_type: str | None


def _detect_type(prop: dict[str, Any]) -> str:
    if "type" in prop:
        return str(prop["type"])
    any_of = prop.get("anyOf", [])
    types = [item.get("type") for item in any_of if isinstance(item, dict)]
    if "number" in types:
        return "number"
    if "boolean" in types:
        return "boolean"
    return "string"


def load_header_create_registry(openapi_file: str) -> tuple[dict[str, FieldMeta], list[str]]:
    spec = json.loads(Path(openapi_file).read_text(encoding="utf-8"))
    schemas = spec.get("components", {}).get("schemas", {})
    create_schema = schemas.get(CREATE_SCHEMA_NAME, {})
    required_fields = create_schema.get("required", [])
    properties = create_schema.get("properties", {})

    registry: dict[str, FieldMeta] = {}
    for name, prop in properties.items():
        enum_values = []
        if "enum" in prop and isinstance(prop["enum"], list):
            enum_values = [str(v) for v in prop["enum"]]

        registry[name] = FieldMeta(
            name=name,
            title=str(prop.get("title", "")),
            description=str(prop.get("description", "")),
            field_type=_detect_type(prop),
            max_length=prop.get("maxLength"),
            enum_values=enum_values,
            required=name in required_fields,
            format_type=prop.get("format"),
        )

    return registry, [str(x) for x in required_fields]
