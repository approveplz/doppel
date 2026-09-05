import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1] / "plugins/model-agents/scripts/model_agents.py"
)
spec = importlib.util.spec_from_file_location("model_agents", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ModelAgentsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="model-agents-test-")
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name) / "home with spaces"
        self.home.mkdir()
        self.fallback = self.home / "AGENTS.md"
        self.fallback.write_text("DEFAULT_ONLY", encoding="utf-8")

    def command(self, name, event=None, success=True):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), name],
            input=json.dumps(event) if event is not None else None,
            text=True,
            capture_output=True,
            env={**os.environ, "CODEX_HOME": str(self.home)},
            timeout=10,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def hook(self, model="gpt-6-astra", event="SessionStart"):
        return json.loads(
            self.command("hook", {"hook_event_name": event, "model": model}).stdout
        )

    def activate(self):
        self.hook()
        self.command("enable")

    def test_cannot_enable_before_startup_hook(self):
        result = self.command("enable", success=False)
        self.assertIn("No startup receipt", result.stderr)
        self.assertFalse((self.home / "AGENTS.override.md").exists())

    def test_inactive_hook_records_startup_without_loading_instructions(self):
        result = self.hook()
        self.assertNotIn("hookSpecificOutput", result)
        self.assertNotIn("DEFAULT_ONLY", json.dumps(result))
        status = json.loads(self.command("status").stdout)
        self.assertTrue(status["startup_observed_for_this_version"])
        self.assertEqual(status["state"], "disabled")

    def test_model_selection_fallback_and_parent_child_isolation(self):
        (self.home / "AGENTS.astra.md").write_text("ASTRA_ONLY", encoding="utf-8")
        (self.home / "AGENTS.sol.md").write_text("SOL_ONLY", encoding="utf-8")
        self.activate()
        for model, event, expected in (
            ("gpt-6-astra", "SessionStart", "ASTRA_ONLY"),
            ("gpt-5.6-sol", "SubagentStart", "SOL_ONLY"),
            ("another-model", "SessionStart", "DEFAULT_ONLY"),
            ("gpt-6-astra", "SessionStart", "ASTRA_ONLY"),
        ):
            with self.subTest(model=model, event=event):
                output = self.hook(model, event)["hookSpecificOutput"]
                self.assertEqual(output["hookEventName"], event)
                context = output["additionalContext"]
                self.assertIn(expected, context)
                for other in {"ASTRA_ONLY", "SOL_ONLY", "DEFAULT_ONLY"} - {expected}:
                    self.assertNotIn(other, context)
        (self.home / "AGENTS.sol.md").unlink()
        self.assertIn(
            "DEFAULT_ONLY",
            self.hook("gpt-5.6-sol", "SubagentStart")["hookSpecificOutput"][
                "additionalContext"
            ],
        )
        self.assertEqual(self.fallback.read_text(), "DEFAULT_ONLY")

    def test_existing_empty_variant_suppresses_fallback(self):
        (self.home / "AGENTS.sol.md").touch()
        self.activate()
        context = self.hook("gpt-5.6-sol")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("AGENTS.sol.md", context)
        self.assertNotIn("DEFAULT_ONLY", context)

    def test_no_files_is_valid(self):
        self.fallback.unlink()
        self.activate()
        self.assertIn(
            "no matching file", self.hook()["hookSpecificOutput"]["additionalContext"]
        )

    def test_enable_disable_are_repeatable_and_preserve_files(self):
        self.activate()
        self.command("enable")
        self.command("disable")
        self.command("disable")
        self.assertFalse((self.home / "AGENTS.override.md").exists())
        self.assertEqual(self.fallback.read_text(), "DEFAULT_ONLY")

    def test_foreign_and_modified_overrides_are_never_overwritten_or_removed(self):
        self.hook()
        override = self.home / "AGENTS.override.md"
        for contents in ("My existing override", module.OVERRIDE + "My addition"):
            override.write_text(contents, encoding="utf-8")
            self.command("enable", success=False)
            self.command("disable", success=False)
            self.assertEqual(override.read_text(), contents)

    def test_symlink_override_is_not_owned_even_with_matching_content(self):
        self.hook()
        target = self.home / "owned-elsewhere.md"
        target.write_text(module.OVERRIDE, encoding="utf-8")
        override = self.home / "AGENTS.override.md"
        override.symlink_to(target)
        self.command("enable", success=False)
        self.command("disable", success=False)
        self.assertTrue(override.is_symlink())
        self.assertEqual(target.read_text(), module.OVERRIDE)

    def test_invalid_or_stale_receipt_cannot_enable(self):
        receipt = module.receipt_path(self.home)
        receipt.parent.mkdir()
        for content in ("{bad", "[]", '{"fingerprint":"old-version"}'):
            receipt.write_text(content, encoding="utf-8")
            self.command("enable", success=False)
        self.assertFalse((self.home / "AGENTS.override.md").exists())

    def test_oversized_or_invalid_variant_does_not_silently_fall_back(self):
        self.activate()
        variant = self.home / "AGENTS.astra.md"
        for content in (b"x" * (module.MAX_BYTES + 1), b"\xff"):
            variant.write_bytes(content)
            result = self.command(
                "hook",
                {"hook_event_name": "SessionStart", "model": "gpt-6-astra"},
                success=False,
            )
            self.assertEqual(result.stdout, "")
            self.assertNotIn("DEFAULT_ONLY", result.stderr)

    def test_invalid_hook_input_does_not_create_receipt(self):
        for event in (
            [],
            {},
            {"hook_event_name": "SessionStart"},
            {"hook_event_name": "Stop", "model": "gpt-6-astra"},
        ):
            self.command("hook", event, success=False)
        self.assertFalse(module.receipt_path(self.home).exists())

    def test_status_reports_paths_not_instruction_contents(self):
        result = json.loads(self.command("status").stdout)
        self.assertEqual(
            result["selection"]["gpt-6-astra"], str(self.fallback.resolve())
        )
        self.assertNotIn("DEFAULT_ONLY", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
