import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    aicore_client_id: str = os.getenv("AICORE_CLIENT_ID", "")
    aicore_client_secret: str = os.getenv("AICORE_CLIENT_SECRET", "")
    aicore_auth_url: str = os.getenv("AICORE_AUTH_URL", "")
    aicore_base_url: str = os.getenv("AICORE_BASE_URL", "")
    aicore_resource_group: str = os.getenv("AICORE_RESOURCE_GROUP", "default")
    aicore_model: str = os.getenv("AICORE_MODEL", "gpt-4o-mini")
    mapping_confidence_threshold: float = float(
        os.getenv("MAPPING_CONFIDENCE_THRESHOLD", "0.80")
    )
    mapping_rules_file: str = os.getenv("MAPPING_RULES_FILE", "data/mapping_rules.json")
    target_openapi_file: str = os.getenv(
        "TARGET_OPENAPI_FILE",
        "plannedOrder/output_structure/OP_PLANNEDORDER_0001.json",
    )


settings = Settings()
