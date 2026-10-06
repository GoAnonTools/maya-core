import unittest
from tempfile import TemporaryDirectory

from app.delegation import (
    DelegationEventType,
    DelegationManager,
    DelegationRequest,
    DelegationStatus,
)
from app.workers.lightning_protocol import LightningEvent, LightningEventType
from app.workers.specialists.coding_worker import CodingSpecialistWorker


class DelegationApprovalTests(unittest.TestCase):
    def request(self, delegation_id="delegation-approval"):
        return DelegationRequest(
            delegation_id=delegation_id,
            task="Run an operation requiring approval",
        )

    def waiting_manager(self, delegation_id="delegation-approval"):
        manager = DelegationManager()
        manager.accept(self.request(delegation_id))
        manager.running(delegation_id)
        event = manager.approval_required(
            delegation_id,
            "approval-1",
            "The operation changes external state.",
        )
        return manager, event

    def test_approval_request_enters_waiting_state(self):
        manager, event = self.waiting_manager()

        self.assertEqual(event.event_type, DelegationEventType.APPROVAL_REQUIRED)
        self.assertEqual(event.status, DelegationStatus.WAITING_APPROVAL)
        self.assertEqual(manager.get_status("delegation-approval"), DelegationStatus.WAITING_APPROVAL)
        self.assertEqual(
            manager.get_pending_approval("delegation-approval").approval_id,
            "approval-1",
        )

    def test_approval_granted(self):
        manager, _ = self.waiting_manager()

        event = manager.approve("delegation-approval", "approval-1")

        self.assertEqual(event.status, DelegationStatus.APPROVED)
        self.assertEqual(manager.get_status("delegation-approval"), DelegationStatus.APPROVED)
        with self.assertRaises(KeyError):
            manager.get_pending_approval("delegation-approval")

    def test_approval_denied(self):
        manager, _ = self.waiting_manager()

        event = manager.reject(
            "delegation-approval",
            "approval-1",
            reason="The operation was denied.",
        )

        self.assertEqual(event.status, DelegationStatus.REJECTED)
        self.assertEqual(manager.get_status("delegation-approval"), DelegationStatus.REJECTED)

    def test_cancellation_while_waiting_approval(self):
        manager, _ = self.waiting_manager()

        event = manager.cancel("delegation-approval")

        self.assertEqual(event.status, DelegationStatus.CANCELLED)
        self.assertEqual(manager.get_status("delegation-approval"), DelegationStatus.CANCELLED)
        with self.assertRaises(KeyError):
            manager.get_pending_approval("delegation-approval")

    def test_forwarded_approval_notification_becomes_provider_neutral_event(self):
        event = CodingSpecialistWorker._to_delegation_event(
            LightningEvent(
                delegation_id="delegation-approval",
                event_type=LightningEventType.PROGRESS,
                message="Approval is required.",
                metadata={
                    "approval_required": True,
                    "approval_id": "approval-forwarded",
                },
            )
        )

        self.assertEqual(event.event_type, DelegationEventType.APPROVAL_REQUIRED)
        self.assertEqual(event.status, DelegationStatus.WAITING_APPROVAL)
        self.assertEqual(event.metadata["approval_id"], "approval-forwarded")

    def test_pending_approval_recovers_after_restart(self):
        with TemporaryDirectory() as directory:
            path = f"{directory}/delegations.json"
            first = DelegationManager(persistence_path=path)
            first.accept(self.request("delegation-recovered"))
            first.running("delegation-recovered")
            first.approval_required(
                "delegation-recovered",
                "approval-recovered",
                "Needs review.",
            )

            recovered = DelegationManager(persistence_path=path)

            self.assertEqual(
                recovered.get_status("delegation-recovered"),
                DelegationStatus.WAITING_APPROVAL,
            )
            self.assertEqual(
                recovered.get_pending_approval(
                    "delegation-recovered"
                ).approval_id,
                "approval-recovered",
            )
            self.assertEqual(
                recovered.approve(
                    "delegation-recovered",
                    "approval-recovered",
                ).status,
                DelegationStatus.APPROVED,
            )


if __name__ == "__main__":
    unittest.main()
