import os
import unittest
from unittest.mock import patch

from app.workers.ministral import (
    DEFAULT_MINISTRAL_MODEL,
    MinistralWorker,
    build_ministral_route,
)


class MinistralWorkerTests(unittest.TestCase):
    def test_builds_route_from_configuration(self):
        route = build_ministral_route(
            {
                "services": {
                    "ministral": {
                        "model": "configured-ministral",
                        "endpoint": "https://ministral.example",
                    }
                }
            }
        )

        self.assertEqual(route["model"], "configured-ministral")
        self.assertEqual(route["endpoint"], "https://ministral.example")
        self.assertEqual(route["mode"], "online")

    def test_environment_overrides_configuration(self):
        with patch.dict(
            os.environ,
            {
                "MAYA_MINISTRAL_MODEL": "env-ministral",
                "MAYA_MINISTRAL_ENDPOINT": "https://env.example",
            },
            clear=False,
        ):
            route = build_ministral_route(
                {
                    "services": {
                        "ministral": {
                            "model": "configured-ministral",
                            "endpoint": "https://configured.example",
                        }
                    }
                }
            )

        self.assertEqual(route["model"], "env-ministral")
        self.assertEqual(route["endpoint"], "https://env.example")

    def test_execute_uses_configured_ministral_route(self):
        calls = []

        def send_prompt(context, route):
            calls.append((context, route))
            return {"status": "ok", "message": "Ministral response"}

        worker = MinistralWorker(
            send_prompt_fn=send_prompt,
            settings={
                "services": {
                    "ministral": {
                        "model": "ministral-test",
                        "endpoint": "https://ministral.example",
                    }
                }
            },
        )

        result = worker.execute(
            {"message": "Hello", "maya": {"identity": "Maya"}},
            {"model": "ignored-by-worker"},
        )

        self.assertEqual(result["message"], "Ministral response")
        self.assertEqual(calls[0][1]["model"], "ministral-test")
        self.assertEqual(calls[0][1]["endpoint"], "https://ministral.example")

    def test_stream_uses_existing_streaming_flow(self):
        def stream_prompt(context, route):
            self.assertEqual(route["model"], DEFAULT_MINISTRAL_MODEL)
            yield "Hello"
            yield " Ministral"

        worker = MinistralWorker(
            stream_prompt_fn=stream_prompt,
            settings={"services": {"ministral": {}}},
        )

        self.assertEqual(
            list(worker.stream({"message": "Hello"}, {})),
            ["Hello", " Ministral"],
        )
