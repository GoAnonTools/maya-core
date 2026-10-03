import json
import unittest

import httpx

from app.model_client import send_prompt


class OpenAIProviderIntegrationTests(unittest.TestCase):
    def test_model_client_sends_payload_and_parses_response(self):
        received = {}

        def mock_chat_completions(request):
            received["path"] = request.url.path
            received["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "Hello from mocked Hermes.",
                            },
                        }
                    ],
                },
                request=request,
            )

        context = {
            "maya": {"identity": "Maya"},
            "mode": "online",
            "message": "Hello Maya",
        }
        route = {
            "mode": "online",
            "model": "hermes",
            "provider": "lightning",
            "endpoint": "https://mock.hermes.test",
        }

        with httpx.Client(transport=httpx.MockTransport(mock_chat_completions)) as client:
            result = send_prompt(context, route, client)

        self.assertEqual(received["path"], "/v1/chat/completions")
        self.assertEqual(
            received["payload"],
            {
                "model": "hermes",
                "messages": [
                    {"role": "system", "content": "You are Maya."},
                    {"role": "user", "content": "Hello Maya"},
                ],
            },
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["message"], "Hello from mocked Hermes.")
