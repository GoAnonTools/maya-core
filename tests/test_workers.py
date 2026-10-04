import unittest

from app.workers import OpenAICompatibleWorker, Worker


class WorkerContractTests(unittest.TestCase):
    def test_worker_is_abstract(self):
        self.assertTrue(issubclass(OpenAICompatibleWorker, Worker))


class OpenAICompatibleWorkerTests(unittest.TestCase):
    def test_execute_delegates_to_existing_model_client(self):
        calls = []

        def send_prompt(context, route):
            calls.append((context, route))
            return {
                "status": "ok",
                "model": route["model"],
                "message": "Hello from the worker.",
            }

        context = {"message": "Hello", "maya": {"identity": "Maya"}}
        route = {"model": "hermes", "mode": "online"}
        worker = OpenAICompatibleWorker(send_prompt_fn=send_prompt)

        result = worker.execute(context, route)

        self.assertEqual(result["message"], "Hello from the worker.")
        self.assertEqual(calls, [(context, route)])

    def test_stream_delegates_to_existing_model_client(self):
        calls = []

        def stream_prompt(context, route):
            calls.append((context, route))
            yield "Hello"
            yield " Maya"

        context = {"message": "Hello", "maya": {"identity": "Maya"}}
        route = {"model": "hermes", "mode": "online"}
        worker = OpenAICompatibleWorker(stream_prompt_fn=stream_prompt)

        self.assertEqual(list(worker.stream(context, route)), ["Hello", " Maya"])
        self.assertEqual(calls, [(context, route)])
