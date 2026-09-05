#!/usr/bin/env python3
"""Doppel selects one global instructions file through stock Codex startup hooks."""

import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time


MODEL_FILES = {
    "gpt-5.6-sol": "AGENTS.sol.md",
    "gpt-6-astra": "AGENTS.astra.md",
    "gpt-5.6-luna": "AGENTS.luna.md",
    "gpt-5.6-terra": "AGENTS.terra.md",
}
MAX_BYTES = 64 * 1024
OVERRIDE = """# Doppel global loader

Global instructions are supplied by the doppel startup hook.
Use the doppel context addressed to your current model, not instructions
addressed to another model in inherited conversation history.
If that context is absent, report that Doppel needs setup or repair before
working. Do not guess a model or silently load a different instructions file.
Project instructions still apply normally.
"""


def codex_home():
    return (
        Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        .expanduser()
        .resolve()
    )


def codex_command(home, *args):
    result = subprocess.run(
        [os.environ.get("DOPPEL_CODEX", "codex"), *args],
        env={**os.environ, "CODEX_HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def codex_request(home, method, params):
    """Use the local app-server protocol without creating a model session."""
    with subprocess.Popen(
        [os.environ.get("DOPPEL_CODEX", "codex"), "app-server"],
        env={**os.environ, "CODEX_HOME": str(home)},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ) as process:
        lines = queue.Queue()

        def read_lines():
            for line in process.stdout:
                lines.put(line)
            lines.put(None)

        reader = threading.Thread(target=read_lines, daemon=True)
        reader.start()
        try:
            requests = [
                ("initialize", {"clientInfo": {"name": "doppel", "version": "0.3.0"}}),
                (method, params),
            ]
            for request_id, (request_method, request_params) in enumerate(requests):
                process.stdin.write(
                    json.dumps(
                        {
                            "id": request_id,
                            "method": request_method,
                            "params": request_params,
                        }
                    )
                    + "\n"
                )
                process.stdin.flush()
                deadline = time.monotonic() + 30
                while True:
                    line = lines.get(timeout=max(0, deadline - time.monotonic()))
                    if line is None:
                        raise ValueError(
                            "Codex app-server exited before responding. Check your Codex installation."
                        )
                    response = json.loads(line)
                    if response.get("id") == request_id:
                        if "error" in response:
                            raise ValueError(response["error"]["message"])
                        break
            return response["result"]
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            reader.join(timeout=5)


def check_hooks(home):
    """Require current native hook trust. Never grant trust or run a model turn."""
    result = codex_request(home, "hooks/list", {"cwds": [str(Path.cwd())]})
    hooks = [
        hook
        for entry in result["data"]
        for hook in entry["hooks"]
        if hook.get("pluginId") == "doppel@doppel"
    ]
    if {hook["eventName"] for hook in hooks} != {"sessionStart", "subagentStart"}:
        raise ValueError("Doppel's hooks are missing. Run setup to install the plugin.")
    if any(not hook["enabled"] or hook["trustStatus"] != "trusted" for hook in hooks):
        raise ValueError(
            "Hook approval needed. Open codex, use /hooks to enable and trust both Doppel hooks, "
            "then /quit and rerun this command. No chat message is needed."
        )


def override_state(home):
    path = home / "AGENTS.override.md"
    if path.is_symlink():
        return "conflict"
    try:
        return "enabled" if path.read_text(encoding="utf-8") == OVERRIDE else "conflict"
    except FileNotFoundError:
        return "disabled"


def select_instructions(home, model):
    """Missing variants fall back. Existing empty variants deliberately select nothing."""
    names = [MODEL_FILES[model]] if model in MODEL_FILES else []
    names.append("AGENTS.md")
    for name in names:
        path = home / name
        try:
            with path.open("rb") as source:
                contents = source.read(MAX_BYTES + 1)
        except FileNotFoundError:
            continue
        if len(contents) > MAX_BYTES:
            raise ValueError(f"{path} exceeds the {MAX_BYTES}-byte instruction limit")
        return path, contents.decode("utf-8")
    return None, ""


def run_hook(home, event):
    if not isinstance(event, dict):
        raise ValueError("Hook input must be a JSON object")
    name = event.get("hook_event_name")
    if name not in ("SessionStart", "SubagentStart"):
        raise ValueError(f"Unsupported hook event: {name!r}")
    model = event.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Codex did not supply an active model")
    state = override_state(home)
    if state != "enabled":
        return {
            "systemMessage": (
                "Doppel is installed but inactive. Run the Doppel setup script."
                if state == "disabled"
                else "Doppel found an existing AGENTS.override.md. Run status to review the conflict."
            )
        }
    path, instructions = select_instructions(home, model)
    source = str(path) if path else "none (no matching file or AGENTS.md)"
    context = (
        f"# Doppel global instructions\nModel: {model}\nSource: {source}\n\n"
        "These are the selected global instructions for this agent. "
        "They replace earlier Doppel global instructions for other models. "
        "Follow applicable project instructions where they conflict with these global preferences.\n\n"
        + instructions
    )
    return {"hookSpecificOutput": {"hookEventName": name, "additionalContext": context}}


def enable(home):
    state = override_state(home)
    if state == "conflict":
        raise ValueError(
            "Existing AGENTS.override.md is not owned by Doppel. It was not changed."
        )
    check_hooks(home)
    for model in (*MODEL_FILES, "default"):
        select_instructions(home, model)
    if state == "disabled":
        # Exclusive creation also refuses dangling symlinks and concurrent replacements.
        with (home / "AGENTS.override.md").open("x", encoding="utf-8") as output:
            output.write(OVERRIDE)
    return "Enabled. Start a NEW session. Existing AGENTS.md and model files were not changed."


def setup(home, source):
    if override_state(home) == "conflict":
        raise ValueError(
            "Existing AGENTS.override.md belongs to another loader or was edited. It was not changed."
        )
    # Keep native fallback available while an update waits for renewed approval.
    disable(home)
    print(codex_command(home, "plugin", "marketplace", "add", source).strip())
    installed = json.loads(
        codex_command(home, "plugin", "add", "doppel@doppel", "--json")
    )
    print(f"Installed Doppel {installed['version']}.")
    helper = Path(installed["installedPath"]) / "scripts/doppel.py"
    result = subprocess.run(
        [sys.executable, str(helper), "enable", "--home", str(home)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip().removeprefix("Doppel: "))
    return result.stdout.strip()


def uninstall(home):
    disable(home)
    codex_command(home, "plugin", "remove", "doppel@doppel")
    return "Doppel uninstalled. Start a new session to restore normal AGENTS.md loading. Your instruction files were preserved."


def disable(home):
    state = override_state(home)
    if state == "conflict":
        raise ValueError(
            "AGENTS.override.md was changed or belongs to someone else. It was not removed."
        )
    if state == "enabled":
        (home / "AGENTS.override.md").unlink()
    return "Disabled. Start a NEW session to restore normal global AGENTS.md loading. Instruction files were preserved."


def status(home):
    selected = {}
    for model in (*MODEL_FILES, "other models"):
        path, _ = select_instructions(home, model)
        selected[model] = str(path) if path else None
    state = override_state(home)
    if state == "conflict":
        next_step = (
            "Review the existing AGENTS.override.md. Doppel will not overwrite it."
        )
    elif state == "enabled":
        next_step = "Use /new after activation or instruction changes. Check /hooks if instructions are missing."
    else:
        next_step = (
            "Run the setup command to install Doppel, check hook trust, and activate."
        )
    return {
        "codex_home": str(home),
        "state": state,
        "next_step": next_step,
        "selection": selected,
        "note": "Setup checks current hook trust. Hooks must remain enabled and trusted after activation.",
    }


def main():
    parser = argparse.ArgumentParser(prog="doppel", description=__doc__)
    parser.add_argument(
        "command", choices=("setup", "hook", "enable", "status", "disable", "uninstall")
    )
    parser.add_argument(
        "--source", help="Marketplace source for setup (default: approveplz/doppel)"
    )
    parser.add_argument(
        "--home",
        type=Path,
        help="Codex home for setup/status/removal, not hook execution",
    )
    args = parser.parse_args()
    try:
        if args.source is not None and args.command != "setup":
            raise ValueError("--source is only for setup")
        if args.command == "hook" and args.home is not None:
            raise ValueError(
                "Hooks use CODEX_HOME. --home is only for management commands."
            )
        home = args.home.expanduser().resolve() if args.home else codex_home()
        if args.command == "hook":
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Hook input exceeds 64 KiB")
            result = run_hook(home, json.loads(raw))
        elif args.command == "setup":
            result = setup(home, args.source or "approveplz/doppel")
        else:
            result = {
                "enable": enable,
                "disable": disable,
                "status": status,
                "uninstall": uninstall,
            }[args.command](home)
        print(json.dumps(result) if isinstance(result, dict) else result)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, queue.Empty) as error:
        print(
            f"Doppel: {str(error) or 'Timed out waiting for Codex.'}", file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
