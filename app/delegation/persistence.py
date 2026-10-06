"""Optional local persistence for delegation approval recovery."""

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from app.delegation.models import PendingApproval


class DelegationStatePersistence:
    """Persist enough delegation state to recover pending approvals."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Delegation state must contain an object")
        return value

    def save(
        self,
        *,
        delegation_id: str,
        request: dict[str, Any],
        status: str,
        pending_approval: PendingApproval | None,
    ) -> None:
        records = self.load()
        approval = asdict(pending_approval) if pending_approval else None
        if approval is not None:
            approval["requested_at"] = pending_approval.requested_at.isoformat()
        records[delegation_id] = {
            "request": request,
            "status": status,
            "pending_approval": approval,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(records, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)
