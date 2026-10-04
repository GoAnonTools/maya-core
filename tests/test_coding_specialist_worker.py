import unittest

from app.delegation import DelegationRequest, DelegationStatus
from app.delegation.profile_binding import bind_specialist_profile
from app.workers.specialists.coding_worker import CodingSpecialistWorker


class CodingSpecialistWorkerTests(unittest.TestCase):
    def bound_request(self, **kwargs):
        required_capabilities = kwargs.pop(
            "required_capabilities",
            frozenset({"coding", "testing"}),
        )
        request = DelegationRequest(
            delegation_id="coding-1",
            task="Analyze the repository",
            required_capabilities=required_capabilities,
            **kwargs,
        )
        return bind_specialist_profile(request, "coding-specialist")

    def test_exposes_coding_profile_capabilities(self):
        capability = CodingSpecialistWorker().capability()

        self.assertEqual(capability.worker_id, "coding-specialist")
        self.assertIn("coding", capability.capabilities)
        self.assertIn("repository_access", capability.capabilities)

    def test_accepts_bound_request_and_emits_placeholder_lifecycle(self):
        worker = CodingSpecialistWorker()
        request = self.bound_request()

        self.assertEqual(worker.submit(request), "coding-1")
        events = list(worker.stream_events("coding-1"))

        self.assertEqual(
            [event.status for event in events],
            [
                DelegationStatus.STARTED,
                DelegationStatus.PROGRESS,
                DelegationStatus.COMPLETED,
            ],
        )
        self.assertTrue(events[-1].result["placeholder"])

    def test_rejects_missing_required_capability(self):
        worker = CodingSpecialistWorker()
        request = self.bound_request(
            required_capabilities=frozenset({"unavailable-capability"})
        )

        with self.assertRaisesRegex(ValueError, "missing required capabilities"):
            worker.submit(request)

    def test_rejects_unbound_request(self):
        worker = CodingSpecialistWorker()

        with self.assertRaisesRegex(
            ValueError, "bound to a specialist profile"
        ):
            worker.submit(DelegationRequest("coding-1", "Analyze"))

    def test_cancellation_emits_cancelled_event(self):
        worker = CodingSpecialistWorker()
        worker.submit(self.bound_request())

        worker.cancel("coding-1")
        events = list(worker.stream_events("coding-1"))

        self.assertEqual(
            [event.status for event in events],
            [DelegationStatus.CANCELLED],
        )


if __name__ == "__main__":
    unittest.main()
