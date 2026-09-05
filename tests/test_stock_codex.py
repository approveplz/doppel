"""Opt-in integration tests: stock Codex, installed plugin, local mock Responses server.

Run with DOPPEL_CODEX=/absolute/path/to/codex. No API key or paid calls.
The trust bypass applies only to this test-owned plugin in a temporary CODEX_HOME.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
CODEX = os.environ.get("DOPPEL_CODEX")
MARKETPLACE = os.environ.get("DOPPEL_MARKETPLACE", str(ROOT))


class ResponsesServer(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), ResponsesHandler)
        self.requests = []
        self.delegate = False
        self.spawned = False
        self.child_finished = threading.Event()


class ResponsesHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(request)
        events = [
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "id": "message-test",
                    "content": [{"type": "output_text", "text": "Test complete."}],
                },
            },
            {
                "type": "response.completed",
                "response": {
                    "id": "response-test",
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    },
                },
            },
        ]
        if self.server.delegate:
            if request["model"] == "gpt-5.6-sol":
                self.server.child_finished.set()
            elif not self.server.spawned:
                self.server.spawned = True
                events[0] = {
                    "type": "response.output_item.done",
                    "item": {
                        "type": "function_call",
                        "call_id": "spawn-test",
                        "name": "spawn_agent",
                        "namespace": "collaboration",
                        "arguments": json.dumps(
                            {
                                "task_name": "sol_test",
                                "model": "gpt-5.6-sol",
                                "fork_turns": "none",
                                "message": "Reply with Test complete. Do not use tools.",
                            }
                        ),
                    },
                }
            else:
                self.server.child_finished.wait(10)
        payload = "".join(f"data: {json.dumps(event)}\n\n" for event in events).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@unittest.skipUnless(CODEX, "Set DOPPEL_CODEX to run against stock Codex")
class StockCodexTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="doppel-stock-")
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name) / "codex home"
        self.home.mkdir()
        self.project = Path(self.directory.name) / "project"
        self.project.mkdir()
        (self.home / "AGENTS.md").write_text("FALLBACK_SENTINEL", encoding="utf-8")
        (self.home / "AGENTS.sol.md").write_text("SOL_SENTINEL", encoding="utf-8")
        (self.home / "AGENTS.astra.md").write_text("ASTRA_SENTINEL", encoding="utf-8")
        (self.project / "AGENTS.md").write_text("PROJECT_SENTINEL", encoding="utf-8")
        self.env = {**os.environ, "CODEX_HOME": str(self.home)}
        for name in (
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_ORG_ID",
            "OPENAI_PROJECT_ID",
        ):
            self.env.pop(name, None)
        self.server = ResponsesServer()
        self.addCleanup(self.server.server_close)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.shutdown)
        self.run_codex("plugin", "marketplace", "add", MARKETPLACE)
        installed = json.loads(
            self.run_codex("plugin", "add", "doppel@doppel", "--json").stdout
        )
        self.helper = Path(installed["installedPath"]) / "scripts/doppel.py"

    def run_codex(self, *args):
        result = subprocess.run(
            [CODEX, *args],
            cwd=self.project,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result

    def config_args(self):
        config = {
            "model_provider": "test",
            "model_providers.test.name": "Local test",
            "model_providers.test.base_url": f"http://127.0.0.1:{self.server.server_port}/v1",
            "model_providers.test.wire_api": "responses",
            "model_providers.test.requires_openai_auth": False,
            "model_providers.test.supports_websockets": False,
            "projects." + json.dumps(str(self.project)) + ".trust_level": "trusted",
            "features.shell_tool": False,
            "features.code_mode": False,
            "features.multi_agent_v2": True,
            "agents.enabled": True,
        }
        return [
            arg
            for key, value in config.items()
            for arg in ("-c", f"{key}={json.dumps(value)}")
        ]

    def turn(self, model, trust=True):
        args = [
            "exec",
            "--model",
            model,
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
        ]
        if trust:
            args.append("--dangerously-bypass-hook-trust")
        args += self.config_args()
        self.run_codex(*args, "Reply with Test complete. Do not use tools.")
        return self.server.requests[-1]

    def run_helper(self, command, success=True):
        result = subprocess.run(
            [sys.executable, str(self.helper), command],
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)

    def test_actual_requests_select_one_global_file_and_keep_project_instructions(self):
        initial = self.turn("gpt-6-astra")
        self.assertIn("FALLBACK_SENTINEL", json.dumps(initial["input"]))
        self.run_helper("enable")
        for model, expected in (
            ("gpt-6-astra", "ASTRA_SENTINEL"),
            ("gpt-5.6-sol", "SOL_SENTINEL"),
            ("gpt-5.2", "FALLBACK_SENTINEL"),
        ):
            with self.subTest(model=model):
                request = self.turn(model)
                self.assertEqual(request["model"], model)
                text = json.dumps(request["input"])
                self.assertIn(expected, text)
                self.assertIn("PROJECT_SENTINEL", text)
                for other in {"ASTRA_SENTINEL", "SOL_SENTINEL", "FALLBACK_SENTINEL"} - {
                    expected
                }:
                    self.assertNotIn(other, text)
        self.assertEqual((self.home / "AGENTS.md").read_text(), "FALLBACK_SENTINEL")
        (self.home / "AGENTS.sol.md").unlink()
        self.assertIn(
            "FALLBACK_SENTINEL", json.dumps(self.turn("gpt-5.6-sol")["input"])
        )
        self.run_helper("disable")
        restored = json.dumps(self.turn("gpt-6-astra")["input"])
        self.assertIn("FALLBACK_SENTINEL", restored)
        self.assertNotIn("ASTRA_SENTINEL", restored)

    def test_fresh_sol_subagent_of_astra_receives_only_sol_global_instructions(self):
        self.turn("gpt-6-astra")
        self.run_helper("enable")
        self.server.requests.clear()
        self.server.delegate = True
        self.turn("gpt-6-astra")
        children = [r for r in self.server.requests if r["model"] == "gpt-5.6-sol"]
        tool_results = [
            item
            for r in self.server.requests
            for item in r["input"]
            if item.get("type") == "function_call_output"
        ]
        self.assertTrue(children, json.dumps(tool_results))
        for child in children:
            context = json.dumps(child["input"])
            self.assertIn("SOL_SENTINEL", context)
            self.assertIn("PROJECT_SENTINEL", context)
            self.assertNotIn("ASTRA_SENTINEL", context)
            self.assertNotIn("FALLBACK_SENTINEL", context)
        parent = json.dumps(self.server.requests[0]["input"])
        self.assertIn("ASTRA_SENTINEL", parent)
        self.assertNotIn("SOL_SENTINEL", parent)

    def test_untrusted_hook_cannot_prepare_activation(self):
        self.turn("gpt-6-astra", trust=False)
        self.run_helper("enable", success=False)
        self.assertFalse((self.home / "AGENTS.override.md").exists())

    def test_trusting_hooks_before_first_message_needs_only_one_new_session(self):
        # Exercise the same RPCs as /hooks, without bypassing trust or restarting
        # the thread between approval and its first message.
        with subprocess.Popen(
            [CODEX, "app-server", *self.config_args()],
            cwd=self.project,
            env=self.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ) as process:
            messages = queue.Queue()

            def read_messages():
                for line in process.stdout:
                    messages.put(json.loads(line))
                messages.put(None)

            reader = threading.Thread(target=read_messages, daemon=True)
            reader.start()
            request_id = 0

            def receive(predicate):
                deadline = time.monotonic() + 30
                while True:
                    message = messages.get(timeout=max(0, deadline - time.monotonic()))
                    self.assertIsNotNone(message, "Codex app-server exited")
                    if predicate(message):
                        return message

            def rpc(method, params):
                nonlocal request_id
                request_id += 1
                process.stdin.write(
                    json.dumps({"id": request_id, "method": method, "params": params})
                    + "\n"
                )
                process.stdin.flush()
                response = receive(lambda message: message.get("id") == request_id)
                self.assertNotIn("error", response)
                return response["result"]

            try:
                rpc(
                    "initialize",
                    {"clientInfo": {"name": "doppel-test", "version": "1"}},
                )
                thread = rpc(
                    "thread/start",
                    {
                        "model": "gpt-6-astra",
                        "cwd": str(self.project),
                        "ephemeral": True,
                        "approvalPolicy": "never",
                        "sandbox": "read-only",
                    },
                )["thread"]
                hooks = rpc("hooks/list", {"cwds": [str(self.project)]})["data"][0][
                    "hooks"
                ]
                self.assertEqual(
                    {hook["eventName"] for hook in hooks},
                    {"sessionStart", "subagentStart"},
                )
                self.assertTrue(
                    all(hook["trustStatus"] == "untrusted" for hook in hooks)
                )
                self.run_helper("enable", success=False)
                rpc(
                    "config/batchWrite",
                    {
                        "edits": [
                            {
                                "keyPath": "hooks.state",
                                "value": {
                                    hook["key"]: {"trusted_hash": hook["currentHash"]}
                                    for hook in hooks
                                },
                                "mergeStrategy": "upsert",
                            }
                        ],
                        "reloadUserConfig": True,
                    },
                )
                rpc(
                    "turn/start",
                    {
                        "threadId": thread["id"],
                        "input": [{"type": "text", "text": "Set up Doppel."}],
                    },
                )
                receive(lambda message: message.get("method") == "turn/completed")
                self.assertIn(
                    "FALLBACK_SENTINEL", json.dumps(self.server.requests[-1]["input"])
                )
                self.run_helper("enable")
                self.assertTrue((self.home / "AGENTS.override.md").exists())
            finally:
                process.terminate()
                process.wait(timeout=10)
                reader.join(timeout=5)

        request = self.turn("gpt-6-astra", trust=False)
        context = json.dumps(request["input"])
        self.assertIn("ASTRA_SENTINEL", context)
        self.assertIn("PROJECT_SENTINEL", context)
        self.assertNotIn("FALLBACK_SENTINEL", context)
        self.assertEqual((self.home / "AGENTS.md").read_text(), "FALLBACK_SENTINEL")


if __name__ == "__main__":
    unittest.main()
