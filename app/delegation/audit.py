"""Provider-neutral delegation execution audit records."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from enum import Enum
from typing import Any


class ExecutionAuditStatus(str, Enum):
    """Lifecycle values recorded for a delegated execution."""

    CREATED = "created"
    SELECTED = "selected"
    WAITING_APPROVAL = "waiting_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DelegationTimelineEvent:
    """Operator-facing timestamped entry in an execution timeline."""

    status: str
    timestamp: datetime
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class DelegationExecutionRecord:
    """Internal execution history for one delegation."""

    delegation_id: str
    correlation_id: str | None = None
    executor_selected: str | None = None
    policy_recommendation: str | None = None
    capability_decision: dict[str, Any] = field(default_factory=dict)
    approval_state: str = "not_required"
    status: str = ExecutionAuditStatus.CREATED
    terminal_status: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    timestamps: dict[str, datetime] = field(default_factory=dict)
    error_metadata: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    failure_diagnostics: dict[str, Any] = field(default_factory=dict)
    history: list[str] = field(
        default_factory=lambda: [ExecutionAuditStatus.CREATED]
    )
    timeline: list[DelegationTimelineEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.timeline:
            self.timeline.append(
                DelegationTimelineEvent(
                    status=ExecutionAuditStatus.CREATED,
                    timestamp=self.created_at,
                )
            )

    def summary(self) -> dict[str, Any]:
        """Return a compact operator-readable summary."""
        duration = (
            self.updated_at - self.created_at
        ).total_seconds()
        return {
            "delegation_id": self.delegation_id,
            "correlation_id": self.correlation_id,
            "status": _status_value(self.status),
            "terminal_status": self.terminal_status,
            "executor": self.executor_selected,
            "policy_recommendation": self.policy_recommendation,
            "approval_state": self.approval_state,
            "lifecycle": [_status_value(item) for item in self.history],
            "timeline_events": len(self.timeline),
            "duration_seconds": duration,
            "result_available": self.result is not None,
            "failure": dict(self.failure_diagnostics),
        }

    def operator_summary(self) -> str:
        """Format the summary for logs or operator inspection."""
        summary = self.summary()
        lifecycle = " -> ".join(summary["lifecycle"])
        text = (
            f"delegation={summary['delegation_id']} "
            f"status={summary['status']} "
            f"executor={summary['executor'] or 'none'} "
            f"approval={summary['approval_state']} "
            f"lifecycle={lifecycle}"
        )
        if summary["failure"]:
            text += f" failure={summary['failure']}"
        return text


class ExecutionAuditStore:
    """In-memory audit store with optional JSON persistence."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._records: dict[str, DelegationExecutionRecord] = {}
        self._load()

    def create(self, delegation_id: str) -> DelegationExecutionRecord:
        record = DelegationExecutionRecord(delegation_id=delegation_id)
        self._records[delegation_id] = record
        self._save()
        return record

    def get(self, delegation_id: str) -> DelegationExecutionRecord:
        try:
            return self._records[delegation_id]
        except KeyError as exc:
            raise KeyError(
                f"No execution audit record: {delegation_id}"
            ) from exc

    def records(self) -> list[DelegationExecutionRecord]:
        return list(self._records.values())

    def update(
        self,
        delegation_id: str,
        status: str,
        *,
        executor_selected: str | None = None,
        correlation_id: str | None = None,
        policy_recommendation: str | None = None,
        capability_decision: dict[str, Any] | None = None,
        approval_state: str | None = None,
        error_metadata: dict[str, Any] | None = None,
        terminal_status: str | None = None,
        result: Any = None,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationExecutionRecord:
        record = self.get(delegation_id)
        now = datetime.now(timezone.utc)
        record.status = status
        record.updated_at = now
        if not record.history or record.history[-1] != status:
            record.history.append(status)
        record.timestamps[status] = now
        if executor_selected is not None:
            record.executor_selected = executor_selected
        if correlation_id is not None:
            record.correlation_id = correlation_id
        if policy_recommendation is not None:
            record.policy_recommendation = policy_recommendation
        if capability_decision is not None:
            record.capability_decision = dict(capability_decision)
        if approval_state is not None:
            record.approval_state = approval_state
        if error_metadata is not None:
            record.error_metadata = dict(error_metadata)
        if terminal_status is not None:
            record.terminal_status = terminal_status
        if result is not None:
            record.result = result
        if status == ExecutionAuditStatus.FAILED:
            record.failure_diagnostics = {
                **dict(record.failure_diagnostics),
                **dict(error_metadata or {}),
                **dict(metadata or {}),
                "timestamp": now.isoformat(),
            }
        record.timeline.append(
            DelegationTimelineEvent(
                status=status,
                timestamp=now,
                message=message,
                metadata=dict(metadata or {}),
                error=(error_metadata or {}).get("error"),
            )
        )
        self._save()
        return record

    def summary(self, delegation_id: str) -> dict[str, Any]:
        return self.get(delegation_id).summary()

    def operator_summary(self, delegation_id: str) -> str:
        return self.get(delegation_id).operator_summary()

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Execution audit state must contain an object")
        for delegation_id, data in value.items():
            data = dict(data)
            data["created_at"] = datetime.fromisoformat(data["created_at"])
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
            data["timestamps"] = {
                key: datetime.fromisoformat(timestamp)
                for key, timestamp in data.get("timestamps", {}).items()
            }
            data["timeline"] = [
                DelegationTimelineEvent(
                    status=item["status"],
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    message=item.get("message"),
                    metadata=dict(item.get("metadata", {})),
                    error=item.get("error"),
                )
                for item in data.get("timeline", [])
            ]
            self._records[delegation_id] = DelegationExecutionRecord(**data)

    def _save(self) -> None:
        if self.path is None:
            return
        payload: dict[str, Any] = {}
        for delegation_id, record in self._records.items():
            data = asdict(record)
            data["created_at"] = record.created_at.isoformat()
            data["updated_at"] = record.updated_at.isoformat()
            data["timestamps"] = {
                key: timestamp.isoformat()
                for key, timestamp in record.timestamps.items()
            }
            data["timeline"] = [
                {
                    **asdict(item),
                    "timestamp": item.timestamp.isoformat(),
                }
                for item in record.timeline
            ]
            payload[delegation_id] = data
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)


def _status_value(value: str | Enum) -> str:
    return value.value if isinstance(value, Enum) else value
