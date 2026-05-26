# CLAUDE.md — DynamicMapping

## Project Overview

DynamicMapping is a Python FastAPI microservice that intelligently maps arbitrary CSV/data column headers to SAP PlannedOrder OData target fields. It solves the real-world problem of varying source data structures from different vendors/systems being fed into a fixed SAP schema.

**Core capability:** Three-tier mapping strategy — learned cache → SAP AI Core LLM → fuzzy heuristic fallback.

---

## Repository Structure

```
DynamicMapping/
├── src/                        # Main application source
│   ├── main.py                 # FastAPI app + startup + endpoints
│   ├── config.py               # Settings dataclass (env vars)
│   ├── models.py               # Pydantic request/response models
│   ├── mapper.py               # Core three-tier mapping logic
│   ├── llm_mapper.py           # SAP AI Core LLM integration
│   ├── mapping_store.py        # JSON-file-based persistent cache
│   ├── schema_registry.py      # OpenAPI schema parser for target fields
│   └── validation.py           # Type coercion and payload validation
├── data/
│   └── mapping_rules.json      # Auto-generated learned mapping cache
├── plannedOrder/
│   ├── input/                  # Sample SAP S4 Planned Order data (xlsx, png)
│   └── output_structure/
│       └── OP_PLANNEDORDER_0001.json  # Target SAP OpenAPI schema
├── references/
│   └── utils.py                # Reference-only utility code (not imported by src/)
├── .env.example                # Environment variable template
├── requirements.txt            # Python dependencies
└── README.md                   # End-user documentation
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- SAP AI Core credentials (optional — service degrades gracefully without them)

### Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Then fill in SAP AI Core credentials
```

### Run

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Environment Variables

Defined in `.env.example`. All are optional except the paths which default to repo-relative locations.

| Variable | Default | Purpose |
|---|---|---|
| `AICORE_CLIENT_ID` | — | SAP AI Core OAuth client ID |
| `AICORE_CLIENT_SECRET` | — | SAP AI Core OAuth secret |
| `AICORE_AUTH_URL` | — | Token endpoint URL |
| `AICORE_BASE_URL` | — | AI Core API base URL |
| `AICORE_RESOURCE_GROUP` | `default` | AI Core resource group |
| `AICORE_MODEL` | `gpt-4o-mini` | Model deployment name in AI Core |
| `AICORE_CA_BUNDLE` | — | Path to custom CA bundle for SSL |
| `AICORE_SKIP_SSL_VERIFY` | `false` | Set `true` to disable SSL verification (dev only) |
| `MAPPING_CONFIDENCE_THRESHOLD` | `0.80` | Min confidence to accept a mapping |
| `MAPPING_RULES_FILE` | `data/mapping_rules.json` | Path to learned mappings cache |
| `TARGET_OPENAPI_FILE` | `plannedOrder/output_structure/OP_PLANNEDORDER_0001.json` | SAP OpenAPI schema path |

---

## API Endpoints

### `GET /health`
Returns service status and AI Core connectivity.

### `POST /v1/map-preview`

Maps source headers to SAP PlannedOrder fields.

**Request body (`MapRequest`):**
```json
{
  "source_id": "vendor-abc",
  "headers": ["Order No", "Plant", "Qty"],
  "sample_rows": [["PO-001", "1010", "100"]],
  "user_overrides": {"Order No": "PlannedOrder"},
  "confidence_threshold": 0.85
}
```

**Response (`MapResponse`):**
- `payload`: Mapped field values ready for SAP
- `mapping_decisions`: Per-field decisions with confidence, method, rationale
- `validation`: Required field checks and enum violations

**Precedence:** `user_overrides > mapped_values > defaults`

---

## Architecture & Key Design Decisions

### Three-Tier Mapping Strategy (`src/mapper.py`)

1. **Cache lookup** — checks `mapping_store.json` for an exact fingerprint match (SHA1 of normalized sorted headers). O(1), instant.
2. **LLM mapping** — calls SAP AI Core (Generative AI Hub, OpenAI-compatible) with headers + sample values. Rich semantic understanding. Requires valid credentials.
3. **Fuzzy heuristic** — `SequenceMatcher`-based string similarity between normalized headers and target field names/titles. Always available.

New successful mappings are written back to cache automatically, so the system learns over time.

### Header Normalization (`mapper.normalize_header`)

Headers are lowercased, non-alphanumeric characters replaced with underscores, consecutive underscores collapsed. This creates stable keys regardless of whitespace or punctuation variation.

### Cache Fingerprinting

The cache key is `(source_id, SHA1(sorted normalized headers))`. This means the same source system with the same column set always hits cache, even across restarts.

### Schema Registry (`src/schema_registry.py`)

Parses the SAP OpenAPI spec at startup to extract target field metadata:
- Field name, title, description, type, `maxLength`, enum values, required flag

This metadata drives validation and is passed to the LLM for informed mapping.

### Validation (`src/validation.py`)

After mapping, values are type-coerced before being validated:
- Booleans: `"true"/"false"/"1"/"0"/"yes"/"no"` → `bool`
- Numbers: parsed with decimal precision
- Dates: accepts `YYYY-MM-DD`, `DD-MM-YYYY`, `MM/DD/YYYY`, `DD/MM/YYYY`, `YYYYMMDD`
- Strings: truncated at `maxLength` if specified

---

## Code Conventions

### Style

- Python 3.10+ type hints throughout (`str | None`, `list[str]`)
- PascalCase for classes, snake_case for functions/variables
- Private helpers prefixed with `_` (e.g., `_best_match`, `_coerce_boolean`)
- No comments on obvious code; comments reserved for non-obvious constraints or workarounds

### Models

All request/response types are Pydantic models in `src/models.py`. Add new fields there first.

### Settings

All configuration goes through the frozen `Settings` dataclass in `src/config.py`. Never read `os.environ` directly outside that file.

### Error Handling

The service degrades gracefully:
- If AI Core credentials are missing/invalid → skip LLM, use heuristic
- If LLM call fails → log warning, use heuristic
- If cache file is missing → auto-create it

Do not raise HTTP 500 for mapping failures — return the best available result with low confidence.

### Mapping Store

The cache (`data/mapping_rules.json`) is a flat JSON file. Structure:
```json
{
  "source_id": {
    "<sha1-fingerprint>": {
      "source_header": "TargetField"
    }
  }
}
```
Never write to this file manually; always use `MappingStore` methods.

---

## Testing

No automated test suite exists yet. The `.gitignore` includes `.pytest_cache/` indicating pytest is the intended framework.

Manual testing approach currently used:
- Postman collections against the running service
- Live integration checks against SAP AI Core deployments (evidenced by entries in `mapping_rules.json`)

When adding tests, place them in `tests/` at the repo root and use `pytest`. Test the three mapping tiers independently by mocking `LLMMapper` and `MappingStore`.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.115.0 | Web framework |
| `uvicorn` | 0.30.6 | ASGI server |
| `pydantic` | 2.11.7 | Data validation and settings |
| `python-dotenv` | 1.0.1 | `.env` file loading |
| `sap-ai-sdk-base` | 3.1.6 | SAP AI Core SDK base |
| `sap-ai-sdk-core` | 3.0.11 | SAP AI Core SDK core |
| `sap-ai-sdk-gen` | 5.6.3 | SAP Generative AI Hub client |

---

## What to Avoid

- **Do not** import from `references/utils.py` — it is reference material from another project, not part of this service.
- **Do not** hardcode SAP field names outside `schema_registry.py` — the OpenAPI spec is the source of truth.
- **Do not** add a database dependency for the mapping cache — the JSON file store is intentional (simple, portable, auditable).
- **Do not** break the graceful degradation pattern — LLM failures must always fall through to heuristic, never surface as 5xx errors.
- **Do not** commit `.env` — it is gitignored; only `.env.example` should be in source control.
