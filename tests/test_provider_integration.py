import json
import os
import unittest
from unittest.mock import patch

import httpx

from app.model_client import send_prompt, stream_prompt


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


    def test_model_client_injects_memory_into_system_prompt(self):
        received = {}

        def mock_chat_completions(request):
            received["payload"] = json.loads(request.content)

            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "Memory received.",
                            }
                        }
                    ]
                },
                request=request,
            )

        context = {
            "maya": {
                "identity": "Maya",
            },
            "mode": "online",
            "message": "What AI setup do I prefer?",
            "memory": [
                "David prefers local-first AI",
            ],
        }

        route = {
            "mode": "online",
            "model": "hermes",
            "provider": "lightning",
            "endpoint": "https://mock.hermes.test",
        }

        with httpx.Client(
            transport=httpx.MockTransport(mock_chat_completions)
        ) as client:
            result = send_prompt(
                context,
                route,
                client,
            )

        system_message = received["payload"]["messages"][0]["content"]

        self.assertIn(
            "Memory context:",
            system_message,
        )

        self.assertIn(
            "David prefers local-first AI",
            system_message,
        )

        self.assertEqual(
            result["message"],
            "Memory received.",
        )


    def test_model_client_streams_response_chunks(self):
        def mock_chat_completions(request):
            return httpx.Response(
                200,
                content=(
                    b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
                    b'data: {"choices":[{"delta":{"content":" Maya"}}]}\n\n'
                    b'data: [DONE]\n\n'
                ),
                request=request,
            )

        context = {
            "maya": {
                "identity": "Maya",
            },
            "mode": "online",
            "message": "Hello Maya",
        }

        route = {
            "mode": "online",
            "model": "hermes",
            "provider": "lightning",
            "endpoint": "https://mock.hermes.test",
        }

        with httpx.Client(
            transport=httpx.MockTransport(mock_chat_completions)
        ) as client:
            chunks = list(
                stream_prompt(
                    context,
                    route,
                    client,
                )
            )

        self.assertEqual(
            chunks,
            [
                '{"choices":[{"delta":{"content":"Hello"}}]}',
                '{"choices":[{"delta":{"content":" Maya"}}]}',
            ],
        )


class ModelAuthHeaderTests(unittest.TestCase):
    """MAYA_MODEL_API_KEY gates the bearer header on every model call."""

    CONTEXT = {"maya": {"identity": "Maya"}, "mode": "online", "message": "Hi"}
    ROUTE = {"mode": "online", "model": "claude-sonnet-5-5", "endpoint": "http://127.0.0.1:8101"}

    @staticmethod
    def _handler(received):
        def handle(request):
            received.append(dict(request.headers))
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}]},
                request=request,
            )

        return handle

    def test_sends_bearer_header_when_key_is_set(self):
        received = []
        with patch.dict(os.environ, {"MAYA_MODEL_API_KEY": "test-key-123"}, clear=False), \
                httpx.Client(transport=httpx.MockTransport(self._handler(received))) as client:
            send_prompt(self.CONTEXT, self.ROUTE, client)

        self.assertEqual(received[0].get("authorization"), "Bearer test-key-123")

    def test_sends_no_authorization_header_when_key_is_unset(self):
        received = []
        with patch.dict(os.environ, {"MAYA_MODEL_API_KEY": ""}, clear=False), \
                httpx.Client(transport=httpx.MockTransport(self._handler(received))) as client:
            send_prompt(self.CONTEXT, self.ROUTE, client)

        self.assertNotIn("authorization", received[0])

    def test_streaming_sends_bearer_header_when_key_is_set(self):
        received = []

        def handle(request):
            received.append(dict(request.headers))
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\ndata: [DONE]\n\n',
                request=request,
            )

        with patch.dict(os.environ, {"MAYA_MODEL_API_KEY": "test-key-123"}, clear=False), \
                httpx.Client(transport=httpx.MockTransport(handle)) as client:
            chunks = list(stream_prompt(self.CONTEXT, self.ROUTE, client))

        self.assertEqual(received[0].get("authorization"), "Bearer test-key-123")
        self.assertEqual(len(chunks), 1)
