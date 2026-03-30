# Dynamic Planned Order Mapping Service

FastAPI microservice that maps changing source headers to SAP Planned Order target fields using:
- learned mapping cache
- optional SAP AI Core LLM mapping
- heuristic fuzzy fallback

It supports user hardcoded values via the request field user_overrides.

## Endpoints
- GET /health
- POST /v1/map-preview

## Request Example
{
  "source_id": "vendor-a",
  "headers": ["Planned Order", "Material Number", "Plant", "Qty"],
  "sample_rows": [
    {
      "Planned Order": "1000000123",
      "Material Number": "FG-1001",
      "Plant": "1710",
      "Qty": "25"
    }
  ],
  "user_overrides": {
    "PlannedOrderIsFirm": true
  },
  "confidence_threshold": 0.8
}

## Run
1. Create virtual env and install dependencies.
2. Copy .env.example to .env and set values.
3. Start server:

uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

## Notes
- Precedence order is user_overrides > mapped values > defaults.
- Unknown override keys are rejected and returned in override_decisions.
- Required field validation uses the OpenAPI create schema for PlannedOrderHeader.

## AI Core SSL
- If your environment uses enterprise TLS interception, set AICORE_CA_BUNDLE to your CA bundle path.
- For local debugging only, you can set AICORE_SKIP_SSL_VERIFY=true.
