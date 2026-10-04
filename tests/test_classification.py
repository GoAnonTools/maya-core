import unittest

from app.orchestration import NormalizedRequest
from app.routing import (
    DeterministicTaskClassifier,
    TaskCategory,
    TaskClassification,
)


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.classifier = DeterministicTaskClassifier()

    def test_supports_all_task_categories(self):
        self.assertEqual(TaskCategory.CONVERSATION.value, "conversation")
        self.assertEqual(TaskCategory.CODING.value, "coding")
        self.assertEqual(TaskCategory.RESEARCH.value, "research")
        self.assertEqual(TaskCategory.TOOL_USE.value, "tool_use")
        self.assertEqual(
            TaskCategory.FILE_OPERATION.value,
            "file_operation",
        )

    def test_placeholder_defaults_to_conversation(self):
        classification = self.classifier.classify(
            NormalizedRequest(context={}, route={})
        )

        self.assertIsInstance(classification, TaskClassification)
        self.assertEqual(classification.category, TaskCategory.CONVERSATION)
        self.assertEqual(classification.metadata["source"], "placeholder")

    def test_explicit_normalized_metadata_is_preserved(self):
        classification = self.classifier.classify(
            NormalizedRequest(
                context={},
                route={},
                metadata={"task_category": "coding"},
            )
        )

        self.assertEqual(classification.category, TaskCategory.CODING)
        self.assertEqual(
            classification.reason,
            "explicit normalized request metadata",
        )

    def test_unknown_metadata_keeps_placeholder_default(self):
        classification = self.classifier.classify(
            NormalizedRequest(
                context={},
                route={},
                metadata={"task_category": "unknown"},
            )
        )

        self.assertEqual(classification.category, TaskCategory.CONVERSATION)
