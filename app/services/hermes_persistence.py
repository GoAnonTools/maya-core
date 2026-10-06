"""Small file-backed persistence boundary for Hermes run mappings."""

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from app.services.hermes_errors import HermesPersistenceError
from app.services.hermes_protocol import HermesRunMapping


class HermesRunPersistence:
    """Persist execution/run correlation records as local JSON."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}

        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HermesPersistenceError(
                f"Unable to load Hermes run mappings: {exc}"
            ) from exc

        if not isinstance(value, dict):
            raise HermesPersistenceError(
                "Hermes run mapping store must contain an object"
            )
        return value

    def save(
        self,
        mapping: HermesRunMapping,
        *,
        terminal: bool,
        cancelled: bool,
    ) -> None:
        records = self.load()
        records[mapping.execution_id] = {
            "mapping": asdict(mapping),
            "terminal": terminal,
            "cancelled": cancelled,
        }

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
            temporary.write_text(
                json.dumps(records, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as exc:
            raise HermesPersistenceError(
                f"Unable to save Hermes run mappings: {exc}"
            ) from exc
