import unittest

from app.routing import TaskCategory, required_capabilities_for


class TaskCapabilityMappingTests(unittest.TestCase):
    def test_maps_each_task_category(self):
        expected = {
            TaskCategory.CONVERSATION: frozenset({"conversation"}),
            TaskCategory.CODING: frozenset({"coding"}),
            TaskCategory.RESEARCH: frozenset({"research"}),
            TaskCategory.TOOL_USE: frozenset({"tool_call_proposal"}),
            TaskCategory.FILE_OPERATION: frozenset({"filesystem_read"}),
        }

        for category, capabilities in expected.items():
            with self.subTest(category=category):
                self.assertEqual(
                    required_capabilities_for(category),
                    capabilities,
                )

    def test_mapping_results_are_immutable(self):
        capabilities = required_capabilities_for(TaskCategory.CODING)

        with self.assertRaises(AttributeError):
            capabilities.add("conversation")
