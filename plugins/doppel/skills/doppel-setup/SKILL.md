---
name: doppel-setup
description: Set up, inspect, or remove the Doppel plugin when the user asks to manage it. Not needed for ordinary coding or editing instruction content.
---

# Doppel management

Doppel works through a standalone script. A setup conversation is optional.
The bundled script is `../../scripts/doppel.py` relative to this directory.
Resolve its absolute path and run it with `python3`. It respects `CODEX_HOME`,
otherwise `~/.codex`.

- To inspect, run `status`. Report selected filenames and the next step.
- To activate an installed plugin, run `enable` only when the user asks.
- To install or update, run `setup` only when requested.
- To pause, run `disable`. To remove, run `uninstall`, which disables first.

Activation checks current native hook trust and creates `AGENTS.override.md`.
It does not change existing instruction files. If approval is needed, ask the
user to enable and trust both Doppel hooks in Codex `/hooks`, then retry.
Never grant hook trust or edit Codex's trust configuration for the user.
No startup message, model call, or receipt is required.

Respect override conflicts. Do not overwrite, move, or remove another loader's
or the user's override. Report the conflict and let the user decide.

Astra, Sol, Luna, and Terra use `AGENTS.astra.md`, `AGENTS.sol.md`,
`AGENTS.luna.md`, and `AGENTS.terra.md`. Missing variants use `AGENTS.md`.
Do not generate or rewrite these files unless asked.

Start a new session after activation or instruction changes. Use fresh
subagents without inherited history when changing models. Doppel cannot
remove prior instructions, enforce obedience, or cover internal system agents.
Hooks must remain enabled and trusted. If they stop running, use `disable` to
restore normal global loading.
