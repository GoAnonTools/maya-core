import unittest

from app.delegation import (
    DelegationRequest,
    bind_specialist_profile,
)
from app.workers.capabilities import WorkerRole
from app.workers.specialists.catalog import SpecialistCapabilityCatalog


class DelegationProfileBindingTests(unittest.TestCase):
    def test_binds_coding_profile_snapshot_to_request(self):
        request = DelegationRequest(
            delegation_id="delegation-1",
            task="Review code",
            request_id="request-1",
            session_id="session-1",
        )

        bound = bind_specialist_profile(
            request,
            "coding-specialist",
            SpecialistCapabilityCatalog(),
        )

        self.assertEqual(bound.delegation_id, request.delegation_id)
        self.assertEqual(bound.specialist_id, "coding-specialist")
        self.assertEqual(bound.specialist_role, WorkerRole.SPECIALIST)
        self.assertIn("coding", bound.specialist_capabilities)
        self.assertIn("filesystem_read", bound.specialist_capabilities)
        self.assertEqual(
            bound.specialist_metadata["display_name"],
            "Coding Specialist",
        )
        self.assertFalse(bound.specialist_metadata["availability"])

    def test_binding_does_not_change_original_request(self):
        request = DelegationRequest("delegation-2", "Analyze repository")

        bound = bind_specialist_profile(request, "coding-specialist")

        self.assertIsNone(request.specialist_id)
        self.assertIsNone(request.specialist_role)
        self.assertEqual(request.specialist_capabilities, frozenset())
        self.assertEqual(bound.task, request.task)

    def test_unknown_profile_is_rejected(self):
        request = DelegationRequest("delegation-3", "Research")

        with self.assertRaises(KeyError):
            bind_specialist_profile(request, "missing-specialist")
