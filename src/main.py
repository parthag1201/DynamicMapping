from __future__ import annotations

import logging
import os

from fastapi import FastAPI

from src.config import settings
from src.mapper import (
    apply_overrides,
    build_mapping_decisions,
    header_fingerprint,
    pick_sample_value,
)
from src.mapping_store import MappingStore
from src.models import MapRequest, MapResponse
from src.schema_registry import load_header_create_registry
from src.validation import coerce_payload, validate_payload

app = FastAPI(title="Dynamic Planned Order Mapper", version="0.1.0")

logger = logging.getLogger("dynamic_mapping.startup")

registry, required_fields = load_header_create_registry(settings.target_openapi_file)
store = MappingStore(settings.mapping_rules_file)

# Setting up ssl bundle for aicore root level access from project
def _set_aicore_ssl_env() -> None:
    ca_bundle = os.getenv("AICORE_CA_BUNDLE", "").strip()
    if ca_bundle:
        os.environ["REQUESTS_CA_BUNDLE"] = ca_bundle
        os.environ["SSL_CERT_FILE"] = ca_bundle

# 
def _matches_model_name(item: object, model_name: str) -> bool:
    if isinstance(item, str):
        return item.strip() == model_name
    if isinstance(item, dict):
        for value in item.values():
            if _matches_model_name(value, model_name):
                return True
        return False
    if isinstance(item, list):
        for value in item:
            if _matches_model_name(value, model_name):
                return True
        return False
    return False


def _aicore_startup_diagnostics() -> None:
    _set_aicore_ssl_env()

    if not (settings.aicore_client_id and settings.aicore_auth_url and settings.aicore_base_url):
        logger.warning("AI Core not fully configured. Check AICORE_CLIENT_ID/AICORE_AUTH_URL/AICORE_BASE_URL")
        return

    try:
        from ai_api_client_sdk.ai_api_v2_client import AIAPIV2Client
    except Exception as exc:
        logger.warning("AI Core SDK unavailable: %s", exc)
        return

    verify_ssl: bool | str = True
    ca_bundle = os.getenv("AICORE_CA_BUNDLE", "").strip()
    if os.getenv("AICORE_SKIP_SSL_VERIFY", "false").lower() == "true":
        verify_ssl = False
    elif ca_bundle:
        verify_ssl = ca_bundle

    try:
        client = AIAPIV2Client(
            base_url=settings.aicore_base_url,
            auth_url=settings.aicore_auth_url,
            client_id=settings.aicore_client_id,
            client_secret=settings.aicore_client_secret,
            resource_group=settings.aicore_resource_group,
            verify_ssl=verify_ssl,
        )
        deployments = client.deployment.query(top=200)
        resources = getattr(deployments, "resources", []) or []

        deployment_found = False
        for deployment in resources:
            if _matches_model_name(getattr(deployment, "__dict__", {}), settings.aicore_model):
                deployment_found = True
                break
            if _matches_model_name(str(deployment), settings.aicore_model):
                deployment_found = True
                break

        if deployment_found:
            logger.info(
                "AI Core diagnostics OK: SDK reachable and model '%s' appears in deployments (%d total)",
                settings.aicore_model,
                len(resources),
            )
        else:
            logger.warning(
                "AI Core reachable but configured model '%s' not found in deployments (%d total).",
                settings.aicore_model,
                len(resources),
            )
    except Exception as exc:
        logger.warning("AI Core diagnostics failed: %s", exc)


@app.on_event("startup")
def startup_checks() -> None:
    _aicore_startup_diagnostics()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/map-preview", response_model=MapResponse)
def map_preview(request: MapRequest) -> MapResponse:
    threshold = (
        request.confidence_threshold
        if request.confidence_threshold is not None
        else settings.mapping_confidence_threshold
    )

    fingerprint = header_fingerprint(request.headers)
    cached_rules = store.get_rules(request.source_id, fingerprint)

    decisions = build_mapping_decisions(
        headers=request.headers,
        sample_rows=request.sample_rows,
        registry=registry,
        threshold=threshold,
        model_name=settings.aicore_model,
        cached_rules=cached_rules,
    )

    payload: dict[str, object] = {}
    accepted_rules: dict[str, str] = {}

    for decision in decisions:
        if decision.status != "accepted" or decision.target_field is None:
            continue
        value = pick_sample_value(request.sample_rows, decision.source_header)
        if value is None:
            continue
        payload[decision.target_field] = value
        accepted_rules[decision.source_header] = decision.target_field

    payload, override_decisions = apply_overrides(payload, request.user_overrides, registry)
    payload, coercion_errors = coerce_payload(payload, registry)

    validation = validate_payload(payload, registry, required_fields)
    validation.errors.extend(coercion_errors)
    validation.valid = not validation.errors

    if accepted_rules:
        store.set_rules(request.source_id, fingerprint, accepted_rules)

    rejected = [x for x in decisions if x.status == "rejected"]
    return MapResponse(
        api_path="/PlannedOrderHeader",
        payload=payload,
        mapping_decisions=decisions,
        rejected_mappings=rejected,
        override_decisions=override_decisions,
        validation=validation,
    )
