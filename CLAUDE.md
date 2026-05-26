# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then populate values

# Run server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Debug LLM calls
MAPPING_DEBUG=true uvicorn src.main:app --reload
```

There is no test suite or linter configured in this repo.

## Architecture

This is a FastAPI microservice (`POST /v1/map-preview`) that maps arbitrary source spreadsheet headers to fixed SAP Planned Order target fields defined by an OpenAPI schema.

**Mapping pipeline** (`src/mapper.py` → `src/main.py`):

1. **Cache** (`src/mapping_store.py`): Checks `data/mapping_rules.json` for a previously accepted mapping for the same `source_id` + header fingerprint (SHA-1 of sorted normalized headers). Cache entries are persisted after each successful response.

2. **LLM** (`src/llm_mapper.py`): Calls SAP AI Core via the `gen_ai_hub` SDK (OpenAI-compatible interface). Requests JSON with `response_format={"type": "json_object"}` and falls back to a plain call if the backend doesn't support it. Only runs if AI Core env vars are configured.

3. **Heuristic** (`src/mapper.py:_best_match`): `difflib.SequenceMatcher` fuzzy match of normalized header text against field name, title, and description from the schema registry.

**Schema registry** (`src/schema_registry.py`): Reads the SAP OData OpenAPI spec at `plannedOrder/output_structure/OP_PLANNEDORDER_0001.json` on startup. Extracts the `PlannedOrderHeaderType-create` schema into a `dict[str, FieldMeta]` that drives all downstream matching, override validation, type coercion, and required-field checking.

**Precedence for the final payload**: `user_overrides` > mapped values > nothing (no defaults are injected). Unknown override keys are rejected and reported in `override_decisions`.

**Key env vars** (see `.env.example`):
- `AICORE_*`: SAP AI Core credentials and endpoint — service degrades to heuristic-only if absent
- `AICORE_CA_BUNDLE` / `AICORE_SKIP_SSL_VERIFY`: SSL handling for enterprise TLS interception
- `MAPPING_CONFIDENCE_THRESHOLD` (default `0.80`): minimum score for a mapping to be accepted
- `MAPPING_RULES_FILE` (default `data/mapping_rules.json`): path to the learned-mapping cache
- `TARGET_OPENAPI_FILE`: path to the SAP OData OpenAPI spec
