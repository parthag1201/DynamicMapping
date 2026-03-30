from __future__ import annotations

import json
from pathlib import Path


class MappingStore:
    def __init__(self, file_path: str):
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, payload: dict) -> None:
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_rules(self, source_id: str, fingerprint: str) -> dict[str, str]:
        data = self.load()
        return data.get(source_id, {}).get(fingerprint, {})

    def set_rules(self, source_id: str, fingerprint: str, rules: dict[str, str]) -> None:
        data = self.load()
        if source_id not in data:
            data[source_id] = {}
        data[source_id][fingerprint] = rules
        self.save(data)
