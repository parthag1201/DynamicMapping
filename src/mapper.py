from __future__ import annotations

import re
from difflib import SequenceMatcher
from hashlib import sha1
from typing import Any

from src.llm_mapper import llm_map_headers
from src.models import MappingDecision, OverrideDecision
from src.schema_registry import FieldMeta


def normalize_header(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered)
    return lowered.strip("_")


def header_fingerprint(headers: list[str]) -> str:
    normalized = sorted(normalize_header(h) for h in headers)
    return sha1("|".join(normalized).encode("utf-8")).hexdigest()


def _field_aliases(meta: FieldMeta) -> list[str]:
    raw = [meta.name, meta.title, meta.description]
    return [normalize_header(x) for x in raw if x]


def _best_match(header: str, registry: dict[str, FieldMeta]) -> tuple[str | None, float]:
    normalized_header = normalize_header(header)
    best_field = None
    best_score = 0.0

    for field_name, meta in registry.items():
        for alias in _field_aliases(meta):
            score = SequenceMatcher(None, normalized_header, alias).ratio()
            if score > best_score:
                best_score = score
                best_field = field_name

    return best_field, best_score


def build_mapping_decisions(
    headers: list[str],
    sample_rows: list[dict[str, Any]],
    registry: dict[str, FieldMeta],
    threshold: float,
    model_name: str,
    cached_rules: dict[str, str],
) -> list[MappingDecision]:
    llm_candidates = llm_map_headers(
        headers=headers,
        sample_rows=sample_rows,
        target_fields=[
            {
                "name": name,
                "title": meta.title,
                "description": meta.description,
            }
            for name, meta in registry.items()
        ],
        model_name=model_name,
    )
    llm_by_header = {
        normalize_header(str(x.get("source_header", ""))): x for x in llm_candidates
    }

    decisions: list[MappingDecision] = []
    for header in headers:
        normalized = normalize_header(header)

        if header in cached_rules:
            target = cached_rules[header]
            score = 1.0
            method = "cache"
            rationale = "Matched from learned mapping store"
        elif normalized in llm_by_header:
            llm_item = llm_by_header[normalized]
            target = llm_item.get("target_field")
            score = float(llm_item.get("confidence", 0.0))
            method = "llm"
            rationale = str(llm_item.get("rationale", ""))
        else:
            target, score = _best_match(header, registry)
            method = "heuristic"
            rationale = "Fuzzy name match against target field metadata"

        status = "accepted" if target in registry and score >= threshold else "rejected"
        if target not in registry:
            target = None
            status = "rejected"

        decisions.append(
            MappingDecision(
                source_header=header,
                target_field=target,
                confidence=round(score, 4),
                method=method,
                rationale=rationale,
                status=status,
            )
        )

    return decisions


def pick_sample_value(sample_rows: list[dict[str, Any]], header: str) -> Any:
    for row in sample_rows:
        if header in row and row[header] not in (None, ""):
            return row[header]
    return None


def apply_overrides(
    payload: dict[str, Any],
    user_overrides: dict[str, Any],
    registry: dict[str, FieldMeta],
) -> tuple[dict[str, Any], list[OverrideDecision]]:
    merged = dict(payload)
    decisions: list[OverrideDecision] = []

    for key, value in user_overrides.items():
        if key not in registry:
            decisions.append(
                OverrideDecision(
                    field=key,
                    status="rejected",
                    reason="Unknown target field",
                )
            )
            continue

        merged[key] = value
        decisions.append(
            OverrideDecision(
                field=key,
                status="applied",
                reason="Override applied with highest precedence",
            )
        )

    return merged, decisions
