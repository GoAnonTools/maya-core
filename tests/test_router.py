import unittest
from unittest.mock import patch

from app.router import select_model


class ModelRouterTests(unittest.TestCase):
    @patch("app.router.load_settings")
    def test_online_mode_selects_hermes(self, load_settings):
        load_settings.return_value = {
            "maya": {"mode": "online"},
            "services": {
                "model": {
                    "provider": "lightning",
                    "model": "NousResearch/Hermes-3-Llama-3.1-8B",
                    "base_url": "http://localhost:8000",
                    "endpoint": None,
                }
            },
        }

        self.assertEqual(
            select_model(),
            {
                "mode": "online",
                "model": "NousResearch/Hermes-3-Llama-3.1-8B",
                "provider": "lightning",
                "base_url": "http://localhost:8000",
                "endpoint": None,
            },
        )

    @patch("app.router.load_settings")
    def test_offline_mode_selects_local_qwen(self, load_settings):
        load_settings.return_value = {
            "maya": {"mode": "offline"},
            "services": {
                "model": {
                    "endpoint": "https://unused.example",
                }
            },
        }

        self.assertEqual(
            select_model(),
            {
                "mode": "offline",
                "model": "qwen_local",
                "provider": "local",
                "base_url": None,
                "endpoint": None,
            },
        )
