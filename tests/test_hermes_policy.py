import os
import unittest
from unittest.mock import patch

from app.delegation import (
    HermesDelegationPolicy,
    HermesRecommendation,
)


class HermesDelegationPolicyTests(unittest.TestCase):
    def test_disabled_by_default(self):
        decision = HermesDelegationPolicy().recommend(
            "Implement a coding fix",
            task_category="coding",
        )

        self.assertEqual(
            decision.recommendation,
            HermesRecommendation.CANDIDATE,
        )
        self.assertFalse(decision.eligible_for_hermes)
        self.assertFalse(decision.hermes_enabled)
        self.assertEqual(decision.metadata["effective_target"], "local")

    def test_coding_task_is_candidate_when_enabled(self):
        decision = HermesDelegationPolicy(enabled=True).recommend(
            "Implement a coding fix",
            task_category="coding",
        )

        self.assertEqual(
            decision.recommendation,
            HermesRecommendation.CANDIDATE,
        )
        self.assertTrue(decision.eligible_for_hermes)

    def test_simple_question_stays_local(self):
        decision = HermesDelegationPolicy(enabled=True).recommend(
            "What time is it?",
            task_category="conversation",
        )

        self.assertEqual(decision.recommendation, HermesRecommendation.LOCAL)
        self.assertFalse(decision.eligible_for_hermes)

    def test_dangerous_task_requires_approval(self):
        decision = HermesDelegationPolicy(enabled=True).recommend(
            "Delete the production database",
            dangerous=True,
        )

        self.assertEqual(
            decision.recommendation,
            HermesRecommendation.APPROVAL_REQUIRED,
        )
        self.assertTrue(decision.approval_required)
        self.assertFalse(decision.eligible_for_hermes)

    def test_unknown_task_uses_local_fallback(self):
        decision = HermesDelegationPolicy(enabled=True).recommend(
            "Do the thing",
        )

        self.assertEqual(decision.recommendation, HermesRecommendation.LOCAL)
        self.assertFalse(decision.eligible_for_hermes)

    def test_missing_permissions_prevent_hermes_recommendation(self):
        decision = HermesDelegationPolicy(enabled=True).recommend(
            "Research the project",
            task_category="research",
            required_permissions=frozenset({"network"}),
            granted_permissions=frozenset(),
        )

        self.assertEqual(decision.recommendation, HermesRecommendation.LOCAL)
        self.assertEqual(decision.missing_permissions, frozenset({"network"}))

    def test_environment_flag_is_opt_in(self):
        with patch.dict(os.environ, {"MAYA_HERMES_ENABLED": "true"}):
            self.assertTrue(HermesDelegationPolicy.from_environment().enabled)

        with patch.dict(os.environ, {"MAYA_HERMES_ENABLED": "false"}):
            self.assertFalse(HermesDelegationPolicy.from_environment().enabled)


if __name__ == "__main__":
    unittest.main()
