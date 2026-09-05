#!/usr/bin/env python3
"""Doppel selects one global instructions file through stock Codex startup hooks."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


MODEL_FILES = {
    "gpt-5.6-sol": "AGENTS.sol.md",
    "gpt-6-astra": "AGENTS.astra.md",
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


def fingerprint():
    root = Path(__file__).resolve().parent.parent
    return hashlib.sha256(
        Path(__file__).read_bytes() + (root / "hooks/hooks.json").read_bytes()
    ).hexdigest()


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


def receipt_path(home):
    return home / "doppel" / "startup.json"


def record_startup(home):
    # Concurrent sessions may start together. Readers must see a complete receipt.
    path = receipt_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        json.dump({"fingerprint": fingerprint()}, output)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def startup_observed(home):
    try:
        receipt = json.loads(receipt_path(home).read_text(encoding="utf-8"))
        return isinstance(receipt, dict) and receipt.get("fingerprint") == fingerprint()
    except (FileNotFoundError, ValueError):
        return False


def run_hook(home, event):
    if not isinstance(event, dict):
        raise ValueError("Hook input must be a JSON object")
    name = event.get("hook_event_name")
    if name not in ("SessionStart", "SubagentStart"):
        raise ValueError(f"Unsupported hook event: {name!r}")
    model = event.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Codex did not supply an active model")
    if name == "SessionStart":
        record_startup(home)
    state = override_state(home)
    if state != "enabled":
        return {
            "systemMessage": (
                "Doppel is ready to enable. Ask to set up Doppel."
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
    if not startup_observed(home):
        raise ValueError(
            "No startup receipt for this plugin version. Trust both hooks in /hooks, "
            "start a new Codex session, then run enable again."
        )
    for model in (*MODEL_FILES, "default"):
        select_instructions(home, model)
    if state == "disabled":
        # Exclusive creation also refuses dangling symlinks and concurrent replacements.
        with (home / "AGENTS.override.md").open("x", encoding="utf-8") as output:
            output.write(OVERRIDE)
    return "Enabled. Start a NEW session. Existing AGENTS.md and model files were not changed."


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
    observed = startup_observed(home)
    if state == "conflict":
        next_step = (
            "Review the existing AGENTS.override.md. Doppel will not overwrite it."
        )
    elif state == "enabled":
        next_step = "Use /new after activation or instruction changes. Check /hooks if instructions are missing."
    elif observed:
        next_step = "Run enable, then use /new to load the selected instructions."
    else:
        next_step = "Trust both hooks in /hooks before your first message, then ask to set up Doppel. If you already sent a message, use /new first."
    return {
        "codex_home": str(home),
        "state": state,
        "startup_observed_for_this_version": observed,
        "next_step": next_step,
        "selection": selected,
        "note": "A receipt proves a past startup, not that hooks are still enabled or trusted. Check /hooks.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("hook", "enable", "status", "disable"))
    parser.add_argument(
        "--home",
        type=Path,
        help="Codex home for setup/status/removal, not hook execution",
    )
    args = parser.parse_args()
    try:
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
        else:
            result = {"enable": enable, "disable": disable, "status": status}[
                args.command
            ](home)
        print(json.dumps(result) if isinstance(result, dict) else result)
        return 0
    except (OSError, ValueError) as error:
        print(f"Doppel: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
