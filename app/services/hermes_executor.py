"""LightningExecutor adapter for an injected Hermes client."""

from collections.abc import Iterator
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.hermes_client import HermesClient
from app.services.hermes_errors import (
    HermesError,
    HermesNetworkError,
    HermesPartialStreamError,
    HermesPersistenceError,
    HermesUnknownTerminalState,
    HermesUnavailableError,
)
from app.services.hermes_persistence import HermesRunPersistence
from app.services.hermes_protocol import (
    HermesEvent,
    HermesEventType,
    HermesJob,
    HermesRunMapping,
)
from app.services.lightning_executor import (
    ExecutorCapabilities,
    LightningExecutor,
    LightningSession,
)
from app.workers.lightning_protocol import (
    LightningEvent,
    LightningEventType,
    LightningJob,
)


class HermesExecutor(LightningExecutor):
    """Translate Lightning jobs and events to and from an Hermes client.

    Without an injected client this executor is disabled. It never creates a
    transport, starts a process, or performs model execution by itself.
    """

    @property
    def backend_name(self) -> str:
        return "hermes"

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "backend": self.backend_name,
            "provider": "hermes",
            "status": "configured" if self._client else "disabled",
            "available": self._client is not None,
            "execution": "client_adapter",
            "external_process": False,
            "model_execution": False,
        }

    def __init__(
        self,
        client: HermesClient | None = None,
        persistence: HermesRunPersistence | None = None,
        persistence_path: str | Path | None = None,
    ) -> None:
        self._client = client
        if persistence is not None and persistence_path is not None:
            raise ValueError("Provide persistence or persistence_path, not both")
        self._persistence = persistence or (
            HermesRunPersistence(persistence_path)
            if persistence_path is not None
            else None
        )
        self._sessions: dict[str, LightningSession] = {}
        self._mappings: dict[str, HermesRunMapping] = {}
        self._seen_event_ids: dict[str, set[str]] = {}
        self._completed_runs = 0
        self._failed_runs = 0
        self._pending_approvals: dict[str, set[str]] = {}
        self._logger = logging.getLogger(__name__)
        self._restore_mappings()

    @property
    def client(self) -> HermesClient | None:
        """Return the injected client, if configured."""
        return self._client

    def is_available(self) -> bool:
        if self._client is None:
            return False

        try:
            health = self._client.health()
        except Exception:
            return False

        return bool(health.get("available", health.get("status") == "healthy"))

    def capabilities(self) -> ExecutorCapabilities:
        """Describe Hermes support without registering or routing to it."""
        return ExecutorCapabilities(
            supported_task_categories=frozenset({"coding", "research"}),
            required_permissions=frozenset(),
            available=self.is_available(),
            version="1",
            metadata={
                "backend": self.backend_name,
                "provider": "hermes",
                "status": "configured" if self._client else "disabled",
                "external_process": False,
                "model_execution": False,
                "version": "1",
            },
        )

    def submit(self, job: LightningJob) -> str:
        if self._client is None:
            raise HermesUnavailableError("Hermes client is not configured")
        if not job.delegation_id.strip():
            raise ValueError("delegation_id must not be empty")
        if not self.is_available():
            raise HermesUnavailableError("Hermes client is unavailable")

        execution_id = f"hermes-execution-{uuid4()}"
        session_id = job.session_id or f"hermes-session-{uuid4()}"
        hermes_job = self._to_hermes_job(job)
        try:
            run_id = self._client.submit(hermes_job)
        except HermesError:
            raise
        except Exception as exc:
            raise HermesNetworkError(f"Hermes submit failed: {exc}") from exc

        self._sessions[execution_id] = LightningSession(
            execution_id=execution_id,
            session_id=session_id,
            job=job,
        )
        self._mappings[execution_id] = HermesRunMapping(
            execution_id=execution_id,
            run_id=run_id,
            delegation_id=job.delegation_id,
            session_id=session_id,
        )
        self._seen_event_ids[execution_id] = set()
        self._persist(execution_id)
        self._logger.info(
            "Hermes run submitted execution_id=%s run_id=%s",
            execution_id,
            run_id,
        )
        return execution_id

    def stream_events(self, execution_id: str) -> Iterator[LightningEvent]:
        session = self.get_session(execution_id)
        mapping = self._get_mapping(execution_id)

        if session.cancelled:
            self._mark_terminal(execution_id, LightningEventType.CANCELLED)
            yield self._lightning_event(
                session,
                LightningEventType.CANCELLED,
                message="Hermes execution cancelled.",
            )
            return

        saw_terminal = False
        try:
            for event in self._client_events(mapping.run_id):
                if session.cancelled:
                    session.terminal = True
                    yield self._lightning_event(
                        session,
                        LightningEventType.CANCELLED,
                        message="Hermes execution cancelled.",
                    )
                    return

                if event.event_id:
                    seen = self._seen_event_ids.setdefault(execution_id, set())
                    if event.event_id in seen:
                        self._logger.debug(
                            "Ignoring duplicate Hermes event_id=%s",
                            event.event_id,
                        )
                        continue
                    seen.add(event.event_id)

                if event.event_type.value == "approval.request":
                    if event.approval_id:
                        self._pending_approvals.setdefault(
                            execution_id, set()
                        ).add(event.approval_id)

                translated = self._to_lightning_event(session, event)
                if translated.event_type in {
                    LightningEventType.COMPLETED,
                    LightningEventType.FAILED,
                    LightningEventType.CANCELLED,
                }:
                    saw_terminal = True
                    self._mark_terminal(execution_id, translated.event_type)
                yield translated
                if session.terminal:
                    return
            if not saw_terminal:
                raise HermesUnknownTerminalState(
                    "Hermes stream ended without a terminal event"
                )
        except HermesError as exc:
            self._mark_terminal(execution_id, LightningEventType.FAILED)
            yield self._lightning_event(
                session,
                LightningEventType.FAILED,
                error=str(exc),
                metadata={
                    **self.metadata,
                    "failure_state": self._failure_state(exc),
                },
            )
        except Exception as exc:
            self._mark_terminal(execution_id, LightningEventType.FAILED)
            yield self._lightning_event(
                session,
                LightningEventType.FAILED,
                error=str(exc),
                metadata={
                    **self.metadata,
                    "failure_state": "network_failure",
                },
            )

    def cancel(self, execution_id: str) -> None:
        session = self.get_session(execution_id)
        mapping = self._get_mapping(execution_id)

        if session.terminal:
            raise ValueError("Cannot cancel a terminal Hermes session")
        if self._client is None:
            raise HermesUnavailableError("Hermes client is not configured")

        try:
            self._client.cancel(mapping.run_id)
        except HermesError:
            raise
        except Exception as exc:
            raise HermesNetworkError(
                f"Hermes cancellation failed: {exc}"
            ) from exc
        session.cancelled = True
        self._persist(execution_id)

    def active_jobs(self) -> int:
        return sum(
            not session.terminal for session in self._sessions.values()
        )

    def get_session(self, execution_id: str) -> LightningSession:
        try:
            return self._sessions[execution_id]
        except KeyError as exc:
            raise KeyError(
                f"Unknown Hermes execution: {execution_id}"
            ) from exc

    def run_mapping(self, execution_id: str) -> HermesRunMapping:
        """Return the run-ID mapping for diagnostics and cancellation."""
        return self._get_mapping(execution_id)

    def health(self) -> dict[str, Any]:
        """Return adapter and injected-client health metadata."""
        if self._client is None:
            return self.metadata

        try:
            client_health = dict(self._client.health())
        except Exception as exc:
            client_health = {
                "available": False,
                "status": "unhealthy",
                "error": str(exc),
            }

        return {**self.metadata, "metrics": self.metrics(), "client": client_health}

    def metrics(self) -> dict[str, int]:
        """Return reliability and operational counters for Hermes runs."""
        return {
            "active_hermes_runs": self.active_jobs(),
            "completed_runs": self._completed_runs,
            "failed_runs": self._failed_runs,
            "pending_approvals": sum(
                len(approvals)
                for approvals in self._pending_approvals.values()
            ),
        }

    def _to_hermes_job(self, job: LightningJob) -> HermesJob:
        metadata = dict(job.metadata)
        task = metadata.pop("task", None)
        return HermesJob(
            delegation_id=job.delegation_id,
            request_id=job.request_id,
            session_id=job.session_id,
            task=task,
            workspace=job.workspace,
            capabilities=job.capabilities,
            permissions=job.permissions,
            metadata=metadata,
        )

    def _client_events(self, run_id: str) -> Iterator[HermesEvent]:
        if self._client is None:
            raise RuntimeError("Hermes client is not configured")
        yield from self._client.stream_events(run_id)

    def _to_lightning_event(
        self,
        session: LightningSession,
        event: HermesEvent,
    ) -> LightningEvent:
        type_mapping = {
            HermesEventType.STARTED: LightningEventType.STARTED,
            HermesEventType.RUN_STARTED: LightningEventType.STARTED,
            HermesEventType.PROGRESS: LightningEventType.PROGRESS,
            HermesEventType.MESSAGE_DELTA: LightningEventType.PROGRESS,
            HermesEventType.TOOL_STARTED: LightningEventType.PROGRESS,
            HermesEventType.TOOL_COMPLETED: LightningEventType.PROGRESS,
            HermesEventType.APPROVAL_REQUIRED: LightningEventType.PROGRESS,
            HermesEventType.APPROVAL_REQUEST: LightningEventType.PROGRESS,
            HermesEventType.COMPLETED: LightningEventType.COMPLETED,
            HermesEventType.RUN_COMPLETED: LightningEventType.COMPLETED,
            HermesEventType.FAILED: LightningEventType.FAILED,
            HermesEventType.RUN_FAILED: LightningEventType.FAILED,
            HermesEventType.CANCELLED: LightningEventType.CANCELLED,
            HermesEventType.RUN_CANCELLED: LightningEventType.CANCELLED,
        }
        lightning_type = type_mapping.get(
            event.event_type,
            LightningEventType.PROGRESS,
        )
        metadata = {
            "backend": self.backend_name,
            "hermes_event_type": event.event_type.value,
            **dict(event.metadata),
        }
        if event.event_type in {
            HermesEventType.APPROVAL_REQUIRED,
            HermesEventType.APPROVAL_REQUEST,
        }:
            metadata["approval_required"] = True
        if event.approval_id is not None:
            metadata["approval_id"] = event.approval_id

        message = event.message or event.delta
        if event.tool_name is not None:
            metadata["tool_name"] = event.tool_name
        if event.tool_call_id is not None:
            metadata["tool_call_id"] = event.tool_call_id

        return self._lightning_event(
            session,
            lightning_type,
            message=message,
            progress=event.progress,
            result=event.result,
            error=event.error,
            metadata=metadata,
        )

    def _lightning_event(
        self,
        session: LightningSession,
        event_type: LightningEventType,
        *,
        message: str | None = None,
        progress: float | None = None,
        result: Any = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LightningEvent:
        return LightningEvent(
            delegation_id=session.job.delegation_id,
            event_type=event_type,
            request_id=session.job.request_id,
            session_id=session.session_id,
            message=message,
            progress=progress,
            result=result,
            error=error,
            metadata=metadata or self.metadata,
        )

    def _mark_terminal(
        self,
        execution_id: str,
        event_type: LightningEventType,
    ) -> None:
        session = self.get_session(execution_id)
        if session.terminal:
            return

        session.terminal = True
        self._pending_approvals.pop(execution_id, None)
        if event_type == LightningEventType.COMPLETED:
            self._completed_runs += 1
        elif event_type == LightningEventType.FAILED:
            self._failed_runs += 1
        self._persist(execution_id)

    def _failure_state(self, error: HermesError) -> str:
        if isinstance(error, HermesUnavailableError):
            return "hermes_unavailable"
        if isinstance(error, HermesPartialStreamError):
            return "partial_stream"
        if isinstance(error, HermesUnknownTerminalState):
            return "unknown_terminal_state"
        if isinstance(error, HermesNetworkError):
            return "network_failure"
        return "hermes_failure"

    def _persist(self, execution_id: str) -> None:
        if self._persistence is None:
            return
        try:
            self._persistence.save(
                self._mappings[execution_id],
                terminal=self._sessions[execution_id].terminal,
                cancelled=self._sessions[execution_id].cancelled,
            )
        except HermesPersistenceError:
            raise

    def _restore_mappings(self) -> None:
        if self._persistence is None:
            return

        for record in self._persistence.load().values():
            mapping_data = record.get("mapping", {})
            try:
                mapping = HermesRunMapping(**mapping_data)
            except TypeError as exc:
                raise HermesPersistenceError(
                    f"Invalid Hermes run mapping: {exc}"
                ) from exc

            job = LightningJob(
                delegation_id=mapping.delegation_id,
                request_id=None,
                session_id=mapping.session_id,
                workspace=None,
            )
            self._mappings[mapping.execution_id] = mapping
            self._sessions[mapping.execution_id] = LightningSession(
                execution_id=mapping.execution_id,
                session_id=mapping.session_id,
                job=job,
                cancelled=bool(record.get("cancelled", False)),
                terminal=bool(record.get("terminal", False)),
            )
            self._seen_event_ids[mapping.execution_id] = set()

    def _get_mapping(self, execution_id: str) -> HermesRunMapping:
        try:
            return self._mappings[execution_id]
        except KeyError as exc:
            raise KeyError(
                f"Unknown Hermes execution: {execution_id}"
            ) from exc
