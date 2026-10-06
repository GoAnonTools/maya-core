"""In-memory delegation lifecycle manager."""

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.delegation.models import (
    DelegationEvent,
    DelegationEventType,
    DelegationRequest,
    DelegationStatus,
    PendingApproval,
)
from app.delegation.persistence import DelegationStatePersistence
from app.delegation.audit import (
    DelegationExecutionRecord,
    ExecutionAuditStatus,
    ExecutionAuditStore,
)
from app.delegation.executor_selection import (
    ExecutorSelector,
    OptInHermesExecutorSelector,
)
from app.services.lightning_executor import (
    InMemoryLightningExecutor,
    LightningExecutor,
)
from app.workers.lightning_protocol import (
    LightningEvent,
    LightningEventType,
    LightningJob,
)
from app.workers.capabilities import WorkerRole
from app.workers.registry import WorkerRegistry
from app.workers.specialist import SpecialistWorker


EventSink = Callable[[DelegationEvent], None]


class DelegationManager:
    """Accept requests and track their provider-neutral lifecycle."""

    _TRANSITIONS = {
        DelegationStatus.PENDING: {
            DelegationStatus.RUNNING,
            DelegationStatus.STARTED,
            DelegationStatus.WAITING_APPROVAL,
            DelegationStatus.FAILED,
            DelegationStatus.CANCELLED,
        },
        DelegationStatus.STARTED: {
            DelegationStatus.RUNNING,
            DelegationStatus.PROGRESS,
            DelegationStatus.WAITING_APPROVAL,
            DelegationStatus.COMPLETED,
            DelegationStatus.FAILED,
            DelegationStatus.CANCELLED,
        },
        DelegationStatus.PROGRESS: {
            DelegationStatus.RUNNING,
            DelegationStatus.PROGRESS,
            DelegationStatus.WAITING_APPROVAL,
            DelegationStatus.COMPLETED,
            DelegationStatus.FAILED,
            DelegationStatus.CANCELLED,
        },
        DelegationStatus.RUNNING: {
            DelegationStatus.PROGRESS,
            DelegationStatus.WAITING_APPROVAL,
            DelegationStatus.COMPLETED,
            DelegationStatus.FAILED,
            DelegationStatus.CANCELLED,
        },
        DelegationStatus.WAITING_APPROVAL: {
            DelegationStatus.APPROVED,
            DelegationStatus.REJECTED,
            DelegationStatus.CANCELLED,
            DelegationStatus.FAILED,
        },
        DelegationStatus.APPROVED: {
            DelegationStatus.STARTED,
            DelegationStatus.RUNNING,
            DelegationStatus.PROGRESS,
            DelegationStatus.COMPLETED,
            DelegationStatus.FAILED,
            DelegationStatus.CANCELLED,
        },
        DelegationStatus.REJECTED: set(),
        DelegationStatus.COMPLETED: set(),
        DelegationStatus.FAILED: set(),
        DelegationStatus.CANCELLED: set(),
    }

    def __init__(
        self,
        event_sink: EventSink | None = None,
        worker_registry: WorkerRegistry | None = None,
        executor_selector: ExecutorSelector | None = None,
        persistence: DelegationStatePersistence | None = None,
        persistence_path: str | Path | None = None,
        audit_store: ExecutionAuditStore | None = None,
        audit_path: str | Path | None = None,
    ) -> None:
        self._requests: dict[str, DelegationRequest] = {}
        self._statuses: dict[str, DelegationStatus] = {}
        self._events: dict[str, list[DelegationEvent]] = {}
        self._event_sink = event_sink
        self._worker_registry = worker_registry
        self._executor_selector = executor_selector
        if audit_store is not None and audit_path is not None:
            raise ValueError("Provide audit_store or audit_path, not both")
        self._audit = audit_store or ExecutionAuditStore(audit_path)
        if persistence is not None and persistence_path is not None:
            raise ValueError("Provide persistence or persistence_path, not both")
        self._persistence = persistence or (
            DelegationStatePersistence(persistence_path)
            if persistence_path is not None
            else None
        )
        self._pending_approvals: dict[str, PendingApproval] = {}
        self._active_workers: dict[
            str,
            tuple[SpecialistWorker, str],
        ] = {}
        self._active_executors: dict[str, tuple[LightningExecutor, str]] = {}
        self._restore_state()

    def accept(self, request: DelegationRequest) -> DelegationEvent:
        """Accept a new request and emit its pending event."""
        if not request.delegation_id.strip():
            raise ValueError("delegation_id must not be empty")

        if not request.task.strip():
            raise ValueError("task must not be empty")

        if request.delegation_id in self._requests:
            raise ValueError(
                f"Delegation already exists: {request.delegation_id}"
            )

        self._requests[request.delegation_id] = request
        self._statuses[request.delegation_id] = DelegationStatus.PENDING
        self._events[request.delegation_id] = []
        self._audit.create(request.delegation_id)
        self._persist(request.delegation_id)

        return self._emit(
            request.delegation_id,
            DelegationStatus.PENDING,
            message="Delegation accepted.",
        )

    def start(
        self,
        delegation_id: str,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Mark an accepted delegation as started."""
        return self._transition(
            delegation_id,
            DelegationStatus.STARTED,
            message=message,
            metadata=metadata,
        )

    def running(
        self,
        delegation_id: str,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Mark a delegation as actively running."""
        return self._transition(
            delegation_id,
            DelegationStatus.RUNNING,
            message=message,
            metadata=metadata,
        )

    def progress(
        self,
        delegation_id: str,
        progress: float,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Record progress for a started delegation."""
        if not 0.0 <= progress <= 1.0:
            raise ValueError("progress must be between 0.0 and 1.0")

        return self._transition(
            delegation_id,
            DelegationStatus.PROGRESS,
            message=message,
            progress=progress,
            metadata=metadata,
        )

    def complete(
        self,
        delegation_id: str,
        result: Any = None,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Mark a delegation as completed."""
        return self._transition(
            delegation_id,
            DelegationStatus.COMPLETED,
            message=message,
            result=result,
            progress=1.0,
            metadata=metadata,
        )

    def fail(
        self,
        delegation_id: str,
        error: str,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Mark a delegation as failed with a provider-neutral error."""
        if not error.strip():
            raise ValueError("error must not be empty")

        return self._transition(
            delegation_id,
            DelegationStatus.FAILED,
            message=message,
            error=error,
            metadata=metadata,
        )

    def approval_required(
        self,
        delegation_id: str,
        approval_id: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Record an approval request without making an approval decision."""
        if not approval_id.strip():
            raise ValueError("approval_id must not be empty")
        if not reason.strip():
            raise ValueError("approval reason must not be empty")

        pending = PendingApproval(
            delegation_id=delegation_id,
            approval_id=approval_id,
            reason=reason,
            metadata=dict(metadata or {}),
        )
        event = self._transition(
            delegation_id,
            DelegationStatus.WAITING_APPROVAL,
            message=reason,
            metadata={
                **dict(metadata or {}),
                "approval_id": approval_id,
                "approval_required": True,
            },
            event_type=DelegationEventType.APPROVAL_REQUIRED,
        )
        self._pending_approvals[delegation_id] = pending
        self._persist(delegation_id)
        self._audit.update(
            delegation_id,
            ExecutionAuditStatus.WAITING_APPROVAL,
            approval_state="pending",
            message=reason,
            metadata=dict(metadata or {}),
        )
        return event

    def approve(
        self,
        delegation_id: str,
        approval_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Record Maya Core's approval decision; do not execute work."""
        self._require_pending_approval(delegation_id, approval_id)
        self._pending_approvals.pop(delegation_id, None)
        event = self._transition(
            delegation_id,
            DelegationStatus.APPROVED,
            message="Approval granted by Maya Core.",
            metadata={"approval_id": approval_id, **dict(metadata or {})},
        )
        self._persist(delegation_id)
        self._audit.update(
            delegation_id,
            ExecutionAuditStatus.WAITING_APPROVAL,
            approval_state="approved",
            message="Approval granted by Maya Core.",
            metadata=dict(metadata or {}),
        )
        return event

    def reject(
        self,
        delegation_id: str,
        approval_id: str,
        reason: str = "Approval denied by Maya Core.",
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Record Maya Core's rejection decision; do not execute work."""
        self._require_pending_approval(delegation_id, approval_id)
        self._pending_approvals.pop(delegation_id, None)
        event = self._transition(
            delegation_id,
            DelegationStatus.REJECTED,
            message=reason,
            metadata={"approval_id": approval_id, **dict(metadata or {})},
        )
        self._persist(delegation_id)
        self._audit.update(
            delegation_id,
            ExecutionAuditStatus.WAITING_APPROVAL,
            approval_state="rejected",
            terminal_status=DelegationStatus.REJECTED.value,
            error_metadata={"reason": reason},
            message=reason,
            metadata=dict(metadata or {}),
        )
        return event

    def get_pending_approval(self, delegation_id: str) -> PendingApproval:
        """Return the pending approval owned by Maya Core."""
        self._require(delegation_id)
        try:
            return self._pending_approvals[delegation_id]
        except KeyError as exc:
            raise KeyError(
                f"No pending approval: {delegation_id}"
            ) from exc

    def execution_record(
        self,
        delegation_id: str,
    ) -> DelegationExecutionRecord:
        """Return the internal execution audit record for a delegation."""
        self._require(delegation_id)
        return self._audit.get(delegation_id)

    def execution_summary(self, delegation_id: str) -> dict[str, Any]:
        """Return an operator-readable structured execution summary."""
        return self.execution_record(delegation_id).summary()

    def operator_summary(self, delegation_id: str) -> str:
        """Return a concise operator-readable execution summary."""
        return self.execution_record(delegation_id).operator_summary()

    def cancel(
        self,
        delegation_id: str,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DelegationEvent:
        """Cancel a pending or active delegation."""
        active = self._active_workers.get(delegation_id)

        if active is not None:
            worker, execution_id = active
            worker.cancel(execution_id)

        active_executor = self._active_executors.get(delegation_id)
        if active_executor is not None:
            executor, execution_id = active_executor
            executor.cancel(execution_id)

        event = self._transition(
            delegation_id,
            DelegationStatus.CANCELLED,
            message=message,
            metadata=metadata,
        )
        self._pending_approvals.pop(delegation_id, None)
        self._active_workers.pop(delegation_id, None)
        self._persist(delegation_id)
        self._audit.update(
            delegation_id,
            ExecutionAuditStatus.CANCELLED,
            approval_state="cancelled",
            terminal_status=DelegationStatus.CANCELLED.value,
            message=message,
            metadata=dict(metadata or {}),
        )
        return event

    def execute(
        self,
        request: DelegationRequest,
        worker_registry: WorkerRegistry | None = None,
    ) -> list[DelegationEvent]:
        """Execute a delegation through an explicitly registered specialist.

        This method coordinates lifecycle and event forwarding only. It does
        not create workers, launch processes, or select a route.
        """
        self.accept(request)
        registry = worker_registry or self._worker_registry
        worker_id = request.selected_worker.get("worker_id")

        if registry is None:
            self.fail(
                request.delegation_id,
                "No specialist worker registry is configured.",
            )
            return self.events(request.delegation_id)

        try:
            capability = registry.get_capability(worker_id)
        except (KeyError, TypeError):
            self.fail(
                request.delegation_id,
                f"No specialist capability is registered: {worker_id}",
            )
            return self.events(request.delegation_id)

        if capability.role.value != "specialist":
            self.fail(
                request.delegation_id,
                f"Selected worker is not specialist: {worker_id}",
            )
            return self.events(request.delegation_id)

        try:
            worker = registry.get_specialist(worker_id)
        except KeyError:
            self.fail(
                request.delegation_id,
                f"No executable specialist worker is registered: {worker_id}",
            )
            return self.events(request.delegation_id)

        if not capability.availability:
            self.fail(
                request.delegation_id,
                f"Specialist worker is unavailable: {worker_id}",
            )
            return self.events(request.delegation_id)

        self.start(request.delegation_id)

        try:
            execution_id = worker.submit(request)
            self._active_workers[request.delegation_id] = (
                worker,
                execution_id,
            )

            terminal = False
            waiting_for_approval = False

            for event in worker.stream_events(execution_id):
                self._forward_event(request.delegation_id, event)

                if event.status in {
                    DelegationStatus.COMPLETED,
                    DelegationStatus.FAILED,
                    DelegationStatus.CANCELLED,
                    DelegationStatus.REJECTED,
                }:
                    terminal = True
                    break

                if event.status == DelegationStatus.WAITING_APPROVAL:
                    terminal = True
                    waiting_for_approval = True
                    break

            if not terminal and self.get_status(request.delegation_id) not in {
                DelegationStatus.CANCELLED,
                DelegationStatus.FAILED,
                DelegationStatus.REJECTED,
                DelegationStatus.WAITING_APPROVAL,
            }:
                self.fail(
                    request.delegation_id,
                    "Specialist worker ended without a terminal event.",
                )

        except Exception as exc:
            if self.get_status(request.delegation_id) not in {
                DelegationStatus.COMPLETED,
                DelegationStatus.FAILED,
                DelegationStatus.CANCELLED,
                DelegationStatus.REJECTED,
                DelegationStatus.WAITING_APPROVAL,
            }:
                self.fail(request.delegation_id, str(exc))
        finally:
            if not waiting_for_approval:
                self._active_workers.pop(request.delegation_id, None)

        return self.events(request.delegation_id)

    def execute_with_executor(
        self,
        request: DelegationRequest,
        *,
        selector: ExecutorSelector | None = None,
        task_category: str | None = None,
        approval_granted: bool = False,
    ) -> list[DelegationEvent]:
        """Explicitly execute through a selected Lightning executor.

        This path is opt-in and independent from ``execute()``, which keeps
        the existing worker-registry behavior. It never selects an executor
        unless a selector is injected or explicitly passed.
        """
        if request.delegation_id not in self._requests:
            self.accept(request)
        elif self._requests[request.delegation_id] != request:
            raise ValueError(
                f"Delegation already exists: {request.delegation_id}"
            )

        approval_granted = approval_granted or (
            self.get_status(request.delegation_id)
            == DelegationStatus.APPROVED
        )
        selected = selector or self._executor_selector
        if selected is None:
            selected = OptInHermesExecutorSelector(
                hermes_executor=InMemoryLightningExecutor(),
                fallback_executor=InMemoryLightningExecutor(),
            )

        selection = selected.select(
            request,
            task_category=task_category,
            approval_granted=approval_granted,
        )
        trace = dict(selection.trace)
        trace["selection_reason"] = selection.reason
        trace["target"] = selection.target
        correlation_id = str(
            request.metadata.get("correlation_id")
            or request.request_id
            or request.delegation_id
        )
        trace["correlation_id"] = correlation_id
        self._audit.update(
            request.delegation_id,
            ExecutionAuditStatus.SELECTED,
            executor_selected=selection.target,
            correlation_id=correlation_id,
            policy_recommendation=trace.get("policy_recommendation"),
            capability_decision={
                key: value
                for key, value in trace.items()
                if (
                    "capabil" in key
                    or "available" in key
                    or "permission" in key
                )
            },
            message=selection.reason,
            metadata=trace,
        )

        if selection.blocked:
            self.approval_required(
                request.delegation_id,
                str(request.metadata.get("approval_id", "approval-" + request.delegation_id)),
                selection.reason or "Approval is required before execution.",
                metadata={"execution_trace": trace},
            )
            return self.events(request.delegation_id)

        executor = selection.executor
        if executor is None:
            self.fail(
                request.delegation_id,
                "Executor selection returned no executable backend.",
                metadata={"execution_trace": trace},
            )
            return self.events(request.delegation_id)

        if not executor.is_available():
            self.fail(
                request.delegation_id,
                f"Selected executor is unavailable: {executor.backend_name}",
                metadata={"execution_trace": trace},
            )
            return self.events(request.delegation_id)

        self.start(
            request.delegation_id,
            metadata={"execution_trace": trace},
        )
        job = LightningJob(
            delegation_id=request.delegation_id,
            request_id=request.request_id,
            session_id=request.session_id,
            workspace=request.metadata.get("workspace"),
            capabilities=request.required_capabilities,
            permissions=frozenset(
                request.metadata.get("granted_permissions", ())
            ),
            metadata={
                **dict(request.metadata),
                "task": request.task,
                "execution_trace": trace,
                "correlation_id": correlation_id,
            },
        )

        try:
            execution_id = executor.submit(job)
            self._active_executors[request.delegation_id] = (
                executor,
                execution_id,
            )
            terminal = False
            waiting_for_approval = False
            for event in executor.stream_events(execution_id):
                forwarded = self._executor_event(
                    event,
                    execution_trace=trace,
                )
                self._forward_event(request.delegation_id, forwarded)
                if forwarded.status in {
                    DelegationStatus.COMPLETED,
                    DelegationStatus.FAILED,
                    DelegationStatus.CANCELLED,
                    DelegationStatus.REJECTED,
                }:
                    terminal = True
                    break
                if forwarded.status == DelegationStatus.WAITING_APPROVAL:
                    terminal = True
                    waiting_for_approval = True
                    break

            if not terminal and self.get_status(request.delegation_id) not in {
                DelegationStatus.CANCELLED,
                DelegationStatus.FAILED,
                DelegationStatus.WAITING_APPROVAL,
            }:
                self.fail(
                    request.delegation_id,
                    "Executor ended without a terminal event.",
                    metadata={"execution_trace": trace},
                )
        except Exception as exc:
            if self.get_status(request.delegation_id) not in {
                DelegationStatus.COMPLETED,
                DelegationStatus.FAILED,
                DelegationStatus.CANCELLED,
                DelegationStatus.WAITING_APPROVAL,
            }:
                self.fail(
                    request.delegation_id,
                    str(exc),
                    metadata={"execution_trace": trace},
                )
        finally:
            if not waiting_for_approval:
                self._active_executors.pop(request.delegation_id, None)

        return self.events(request.delegation_id)

    def get_request(self, delegation_id: str) -> DelegationRequest:
        """Return an accepted delegation request."""
        self._require(delegation_id)
        return self._requests[delegation_id]

    def get_status(self, delegation_id: str) -> DelegationStatus:
        """Return the current lifecycle status."""
        self._require(delegation_id)
        return self._statuses[delegation_id]

    def events(self, delegation_id: str) -> list[DelegationEvent]:
        """Return a copy of the lifecycle event history."""
        self._require(delegation_id)
        return list(self._events[delegation_id])

    def _transition(
        self,
        delegation_id: str,
        status: DelegationStatus,
        *,
        message: str | None = None,
        progress: float | None = None,
        result: Any = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
        event_type: DelegationEventType = DelegationEventType.LIFECYCLE,
    ) -> DelegationEvent:
        current = self._require(delegation_id)

        if status not in self._TRANSITIONS[current]:
            raise ValueError(
                f"Invalid delegation transition: {current.value} -> "
                f"{status.value}"
            )

        return self._emit(
            delegation_id,
            status,
            message=message,
            progress=progress,
            result=result,
            error=error,
            metadata=metadata,
            event_type=event_type,
        )

    def _emit(
        self,
        delegation_id: str,
        status: DelegationStatus,
        *,
        message: str | None = None,
        progress: float | None = None,
        result: Any = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
        event_type: DelegationEventType = DelegationEventType.LIFECYCLE,
    ) -> DelegationEvent:
        event = DelegationEvent(
            delegation_id=delegation_id,
            status=status,
            event_type=event_type,
            message=message,
            progress=progress,
            result=result,
            error=error,
            metadata=dict(metadata or {}),
        )
        self._statuses[delegation_id] = status
        self._events[delegation_id].append(event)
        self._persist(delegation_id)
        self._audit_for_status(
            delegation_id,
            status,
            error=error,
            result=result,
            metadata=metadata,
            message=message,
        )

        if self._event_sink is not None:
            self._event_sink(event)

        return event

    def _forward_event(
        self,
        delegation_id: str,
        event: DelegationEvent,
    ) -> None:
        """Forward a worker event into the manager history and sink."""
        if event.status == DelegationStatus.WAITING_APPROVAL:
            approval_id = event.metadata.get("approval_id")
            if isinstance(approval_id, str):
                self._pending_approvals[delegation_id] = PendingApproval(
                    delegation_id=delegation_id,
                    approval_id=approval_id,
                    reason=event.message or "Approval required.",
                    metadata=dict(event.metadata),
                )
        self._statuses[delegation_id] = event.status
        self._events[delegation_id].append(event)
        self._persist(delegation_id)
        self._audit_for_status(
            delegation_id,
            event.status,
            error=event.error,
            result=event.result,
            metadata=event.metadata,
            message=event.message,
        )

        if self._event_sink is not None:
            self._event_sink(event)

    def _audit_for_status(
        self,
        delegation_id: str,
        status: DelegationStatus,
        *,
        error: str | None = None,
        result: Any = None,
        metadata: dict[str, Any] | None = None,
        message: str | None = None,
    ) -> None:
        if status in {
            DelegationStatus.STARTED,
            DelegationStatus.RUNNING,
            DelegationStatus.PROGRESS,
        }:
            audit_status = ExecutionAuditStatus.RUNNING
        elif status == DelegationStatus.WAITING_APPROVAL:
            audit_status = ExecutionAuditStatus.WAITING_APPROVAL
        elif status == DelegationStatus.COMPLETED:
            audit_status = ExecutionAuditStatus.COMPLETED
        elif status == DelegationStatus.FAILED:
            audit_status = ExecutionAuditStatus.FAILED
        elif status == DelegationStatus.CANCELLED:
            audit_status = ExecutionAuditStatus.CANCELLED
        else:
            return

        error_metadata = None
        if error is not None:
            error_metadata = {
                "error": error,
                **dict(metadata or {}),
            }
        terminal_status = (
            status.value
            if status
            in {
                DelegationStatus.COMPLETED,
                DelegationStatus.FAILED,
                DelegationStatus.CANCELLED,
            }
            else None
        )
        self._audit.update(
            delegation_id,
            audit_status,
            error_metadata=error_metadata,
            terminal_status=terminal_status,
            result=result,
            message=message,
            metadata=metadata,
        )

    @staticmethod
    def _executor_event(
        event: LightningEvent,
        *,
        execution_trace: dict[str, Any],
    ) -> DelegationEvent:
        """Translate executor events into the manager's provider-neutral form."""
        status_by_type = {
            LightningEventType.STARTED: DelegationStatus.STARTED,
            LightningEventType.PROGRESS: DelegationStatus.PROGRESS,
            LightningEventType.COMPLETED: DelegationStatus.COMPLETED,
            LightningEventType.FAILED: DelegationStatus.FAILED,
            LightningEventType.CANCELLED: DelegationStatus.CANCELLED,
        }
        approval_required = bool(event.metadata.get("approval_required"))
        status = (
            DelegationStatus.WAITING_APPROVAL
            if approval_required
            else status_by_type[event.event_type]
        )
        event_type = (
            DelegationEventType.APPROVAL_REQUIRED
            if approval_required
            else DelegationEventType.LIFECYCLE
        )
        return DelegationEvent(
            delegation_id=event.delegation_id,
            status=status,
            event_type=event_type,
            progress=event.progress,
            message=event.message,
            result=event.result,
            error=event.error,
            metadata={
                "execution_trace": execution_trace,
                **dict(event.metadata),
            },
        )

    def _require(self, delegation_id: str) -> DelegationStatus:
        if delegation_id not in self._requests:
            raise KeyError(f"Unknown delegation: {delegation_id}")

        return self._statuses[delegation_id]

    def _require_pending_approval(
        self,
        delegation_id: str,
        approval_id: str,
    ) -> PendingApproval:
        pending = self.get_pending_approval(delegation_id)
        if pending.approval_id != approval_id:
            raise ValueError(
                f"Approval ID does not match pending approval: {approval_id}"
            )
        return pending

    def _persist(self, delegation_id: str) -> None:
        if self._persistence is None or delegation_id not in self._requests:
            return

        request = self._requests[delegation_id]
        serialized = asdict(request)
        serialized["required_capabilities"] = sorted(
            serialized["required_capabilities"]
        )
        serialized["specialist_capabilities"] = sorted(
            serialized["specialist_capabilities"]
        )
        specialist_role = serialized.get("specialist_role")
        if specialist_role is not None:
            serialized["specialist_role"] = specialist_role.value

        self._persistence.save(
            delegation_id=delegation_id,
            request=serialized,
            status=self._statuses[delegation_id].value,
            pending_approval=self._pending_approvals.get(delegation_id),
        )

    def _restore_state(self) -> None:
        if self._persistence is None:
            return

        for delegation_id, record in self._persistence.load().items():
            request_data = dict(record.get("request", {}))
            request_data["required_capabilities"] = frozenset(
                request_data.get("required_capabilities", [])
            )
            request_data["specialist_capabilities"] = frozenset(
                request_data.get("specialist_capabilities", [])
            )
            specialist_role = request_data.get("specialist_role")
            if specialist_role is not None:
                request_data["specialist_role"] = WorkerRole(specialist_role)
            self._requests[delegation_id] = DelegationRequest(**request_data)
            self._statuses[delegation_id] = DelegationStatus(
                record["status"]
            )
            self._events[delegation_id] = []

            approval = record.get("pending_approval")
            if approval is not None:
                approval["requested_at"] = datetime.fromisoformat(
                    approval["requested_at"]
                )
                self._pending_approvals[delegation_id] = PendingApproval(
                    **approval
                )

            try:
                self._audit.get(delegation_id)
            except KeyError:
                self._audit.create(delegation_id)
                if self._statuses[delegation_id] == DelegationStatus.WAITING_APPROVAL:
                    self._audit.update(
                        delegation_id,
                        ExecutionAuditStatus.WAITING_APPROVAL,
                        approval_state="pending",
                    )
