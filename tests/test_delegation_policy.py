import unittest

from app.delegation import (
    ApprovalRequirement,
    DelegationPolicy,
    OperationScope,
)


class DelegationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = DelegationPolicy(
            approval_requirement=ApprovalRequirement.REQUIRED_FOR_MUTATIONS,
            allowed_operations=frozenset(
                {"read_file", "web_search", "write_file"}
            ),
            read_only_operations=frozenset({"read_file", "web_search"}),
            mutating_operations=frozenset({"write_file"}),
            network_allowed=True,
        )

    def test_describes_read_only_and_mutating_scopes(self):
        self.assertEqual(
            self.policy.operation_scope("read_file"),
            OperationScope.READ_ONLY,
        )
        self.assertEqual(
            self.policy.operation_scope("write_file"),
            OperationScope.MUTATING,
        )
        self.assertTrue(self.policy.is_operation_allowed("web_search"))

    def test_requires_approval_for_mutations_only(self):
        self.assertFalse(self.policy.requires_approval("read_file"))
        self.assertTrue(self.policy.requires_approval("write_file"))

    def test_describes_network_permission(self):
        self.assertTrue(self.policy.allows_network())
        self.assertFalse(
            self.policy.requires_approval("web_search", uses_network=True)
        )

    def test_disallowed_operations_are_rejected(self):
        self.assertFalse(self.policy.is_operation_allowed("send_email"))

        with self.assertRaises(PermissionError):
            self.policy.requires_approval("send_email")

    def test_network_denial_is_distinct_from_approval(self):
        policy = DelegationPolicy(
            approval_requirement=ApprovalRequirement.REQUIRED_FOR_NETWORK,
            allowed_operations=frozenset({"web_search"}),
            read_only_operations=frozenset({"web_search"}),
            network_allowed=False,
        )

        with self.assertRaises(PermissionError):
            policy.requires_approval("web_search", uses_network=True)

    def test_unknown_scope_is_rejected(self):
        policy = DelegationPolicy(
            allowed_operations=frozenset({"unknown"}),
        )

        with self.assertRaises(ValueError):
            policy.operation_scope("unknown")

    def test_always_required_policy(self):
        policy = DelegationPolicy(
            approval_requirement=ApprovalRequirement.REQUIRED,
            allowed_operations=frozenset({"read_file"}),
            read_only_operations=frozenset({"read_file"}),
        )

        self.assertTrue(policy.requires_approval("read_file"))
