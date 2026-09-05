"""Opt-in integration tests: stock Codex, installed plugin, local mock Responses server.

Run with DOPPEL_CODEX=/absolute/path/to/codex. No API key or paid calls.
Hook approval uses native RPCs only for this test-owned plugin in a temporary CODEX_HOME.
"""

import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
CODEX = os.environ.get("DOPPEL_CODEX")
MARKETPLACE = os.environ.get("DOPPEL_MARKETPLACE", str(ROOT))
SCRIPT = ROOT / "plugins/doppel/scripts/doppel.py"
spec = importlib.util.spec_from_file_location("doppel", SCRIPT)
doppel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doppel)


class ResponsesServer(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), ResponsesHandler)
        self.requests = []
        self.delegate = False
        self.child_model = "gpt-5.6-sol"
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
            if request["model"] == self.server.child_model:
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
                                "model": self.server.child_model,
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
        (self.home / "AGENTS.luna.md").write_text("LUNA_SENTINEL", encoding="utf-8")
        (self.home / "AGENTS.terra.md").write_text("TERRA_SENTINEL", encoding="utf-8")
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
        self.helper = Path(self.directory.name) / "doppel"
        shutil.copyfile(SCRIPT, self.helper)
        pending = self.run_helper("setup", "--source", MARKETPLACE, success=False)
        self.assertIn("Hook approval needed", pending.stderr)
        self.assertFalse((self.home / "AGENTS.override.md").exists())
        self.assertEqual(self.server.requests, [])

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

    def turn(self, model):
        args = [
            "exec",
            "--model",
            model,
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
        ]
        args += self.config_args()
        self.run_codex(*args, "Reply with Test complete. Do not use tools.")
        return self.server.requests[-1]

    def run_helper(self, command, *args, success=True):
        result = subprocess.run(
            [sys.executable, str(self.helper), command, *args],
            cwd=self.project,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=90,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def hooks(self):
        return doppel.codex_request(
            self.home, "hooks/list", {"cwds": [str(self.project)]}
        )["data"][0]["hooks"]

    def approve_hooks(self):
        # The same explicit trust operation as /hooks, only in a test-owned home.
        doppel.codex_request(
            self.home,
            "config/batchWrite",
            {
                "edits": [
                    {
                        "keyPath": "hooks.state",
                        "value": {
                            hook["key"]: {"trusted_hash": hook["currentHash"]}
                            for hook in self.hooks()
                        },
                        "mergeStrategy": "upsert",
                    }
                ],
                "reloadUserConfig": True,
            },
        )

    def test_actual_requests_select_one_global_file_and_keep_project_instructions(self):
        initial = self.turn("gpt-6-astra")
        self.assertIn("FALLBACK_SENTINEL", json.dumps(initial["input"]))
        self.approve_hooks()
        self.run_helper("enable")
        for model, expected in (
            ("gpt-6-astra", "ASTRA_SENTINEL"),
            ("gpt-5.6-sol", "SOL_SENTINEL"),
            ("gpt-5.6-luna", "LUNA_SENTINEL"),
            ("gpt-5.6-terra", "TERRA_SENTINEL"),
            ("gpt-5.2", "FALLBACK_SENTINEL"),
        ):
            with self.subTest(model=model):
                request = self.turn(model)
                self.assertEqual(request["model"], model)
                text = json.dumps(request["input"])
                self.assertIn(expected, text)
                self.assertIn("PROJECT_SENTINEL", text)
                for other in {
                    "ASTRA_SENTINEL",
                    "SOL_SENTINEL",
                    "LUNA_SENTINEL",
                    "TERRA_SENTINEL",
                    "FALLBACK_SENTINEL",
                } - {expected}:
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

    def test_fresh_subagents_receive_only_their_own_global_instructions(self):
        self.approve_hooks()
        self.run_helper("enable")
        for model, expected in (
            ("gpt-5.6-sol", "SOL_SENTINEL"),
            ("gpt-5.6-luna", "LUNA_SENTINEL"),
            ("gpt-5.6-terra", "TERRA_SENTINEL"),
        ):
            with self.subTest(model=model):
                self.server.requests.clear()
                self.server.delegate = True
                self.server.child_model = model
                self.server.spawned = False
                self.server.child_finished.clear()
                self.turn("gpt-6-astra")
                children = [r for r in self.server.requests if r["model"] == model]
                self.assertTrue(children, json.dumps(self.server.requests))
                for child in children:
                    context = json.dumps(child["input"])
                    self.assertIn(expected, context)
                    self.assertIn("PROJECT_SENTINEL", context)
                    for other in {
                        "ASTRA_SENTINEL",
                        "SOL_SENTINEL",
                        "LUNA_SENTINEL",
                        "TERRA_SENTINEL",
                        "FALLBACK_SENTINEL",
                    } - {expected}:
                        self.assertNotIn(other, context)

    def test_script_setup_resumes_after_approval_without_a_model_call(self):
        hooks = self.hooks()
        self.assertEqual(
            {hook["eventName"] for hook in hooks}, {"sessionStart", "subagentStart"}
        )
        self.assertTrue(all(hook["trustStatus"] == "untrusted" for hook in hooks))
        self.approve_hooks()
        self.run_helper("setup", "--source", MARKETPLACE)
        self.run_helper("setup", "--source", MARKETPLACE)
        self.assertEqual(self.server.requests, [])
        self.assertTrue((self.home / "AGENTS.override.md").exists())
        request = self.turn("gpt-5.6-luna")
        context = json.dumps(request["input"])
        self.assertIn("LUNA_SENTINEL", context)
        self.assertNotIn("FALLBACK_SENTINEL", context)
        self.run_helper("uninstall")
        restored = json.dumps(self.turn("gpt-5.6-luna")["input"])
        self.assertIn("FALLBACK_SENTINEL", restored)
        self.assertNotIn("LUNA_SENTINEL", restored)
        self.assertEqual((self.home / "AGENTS.md").read_text(), "FALLBACK_SENTINEL")
        self.assertFalse(
            json.loads(self.run_codex("plugin", "list", "--json").stdout)["installed"]
        )

    def test_update_waiting_for_approval_restores_native_fallback(self):
        self.approve_hooks()
        self.run_helper("enable")
        self.turn("gpt-6-astra")
        hook = self.hooks()[0]
        doppel.codex_request(
            self.home,
            "config/batchWrite",
            {
                "edits": [
                    {
                        "keyPath": "hooks.state",
                        "value": {hook["key"]: {"trusted_hash": "revoked"}},
                        "mergeStrategy": "upsert",
                    }
                ],
                "reloadUserConfig": True,
            },
        )
        self.run_helper("setup", "--source", MARKETPLACE, success=False)
        self.assertFalse((self.home / "AGENTS.override.md").exists())
        context = json.dumps(self.turn("gpt-6-astra")["input"])
        self.assertIn("FALLBACK_SENTINEL", context)
        self.assertNotIn("ASTRA_SENTINEL", context)


if __name__ == "__main__":
    unittest.main()
