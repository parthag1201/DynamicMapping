from __future__ import annotations

import json
import os
import re
import ssl
from typing import Any

from src.config import settings


def _debug(msg: str) -> None:
    if os.getenv("MAPPING_DEBUG", "false").lower() == "true":
        print(f"[llm_mapper] {msg}")


def _ensure_aicore_env() -> None:
    # Keep runtime env aligned with loaded config values.
    if settings.aicore_client_id:
        os.environ["AICORE_CLIENT_ID"] = settings.aicore_client_id
    if settings.aicore_client_secret:
        os.environ["AICORE_CLIENT_SECRET"] = settings.aicore_client_secret
    if settings.aicore_auth_url:
        os.environ["AICORE_AUTH_URL"] = settings.aicore_auth_url
    if settings.aicore_base_url:
        os.environ["AICORE_BASE_URL"] = settings.aicore_base_url
    if settings.aicore_resource_group:
        os.environ["AICORE_RESOURCE_GROUP"] = settings.aicore_resource_group

    ca_bundle = os.getenv("AICORE_CA_BUNDLE", "").strip()
    if ca_bundle:
        # Let underlying HTTP clients trust a custom enterprise CA chain.
        os.environ["REQUESTS_CA_BUNDLE"] = ca_bundle
        os.environ["SSL_CERT_FILE"] = ca_bundle

    # Last-resort local debug mode only.
    if os.getenv("AICORE_SKIP_SSL_VERIFY", "false").lower() == "true":
        _debug("AICORE_SKIP_SSL_VERIFY enabled; TLS verification disabled")
        ssl._create_default_https_context = ssl._create_unverified_context


def _extract_json_payload(text: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    # Handle markdown-wrapped JSON responses.
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fenced:
        try:
            payload = json.loads(fenced.group(1))
            if isinstance(payload, dict):
                return payload
        except Exception:
            return None

    return None


def llm_map_headers(
    headers: list[str],
    sample_rows: list[dict[str, Any]],
    target_fields: list[dict[str, str]],
    model_name: str,
) -> list[dict[str, Any]]:
    _ensure_aicore_env()

    try:
        from gen_ai_hub.proxy.native.openai import chat
    except Exception as exc:
        _debug(f"gen_ai_hub import failed: {exc}")
        return []

    prompt = {
        "headers": headers,
        "sample_rows": sample_rows[:3],
        "target_fields": target_fields,
        "task": (
            "Map source headers to target field names. Return JSON with key 'mappings' "
            "as list of objects containing: source_header, target_field, confidence, rationale."
        ),
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You map source headers to target fields. "
                "Return valid JSON only with key 'mappings'."
            ),
        },
        {"role": "user", "content": json.dumps(prompt)},
    ]

    try:
        # Preferred: strict JSON mode if supported by the backend.
        response = chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        _debug(f"json mode call failed, retrying without response_format: {exc}")
        # Fallback for model backends not supporting response_format.
        try:
            response = chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0,
            )
        except Exception as inner_exc:
            _debug(f"standard call failed: {inner_exc}")
            return []

    try:
        content = response.choices[0].message.content
        if isinstance(content, list):
            content = " ".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        payload = _extract_json_payload(str(content))
        if not payload:
            _debug("model response was not valid JSON")
            return []
        mappings = payload.get("mappings", [])
        return mappings if isinstance(mappings, list) else []
    except Exception as exc:
        _debug(f"response parse failed: {exc}")
        return []
