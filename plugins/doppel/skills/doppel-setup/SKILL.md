---
name: doppel-setup
description: Set up, inspect, or remove the Doppel plugin for model-specific global AGENTS instructions in Codex. Use when the user asks to configure this plugin, not for ordinary coding or editing instruction content.
---

# Doppel setup

The bundled helper is `../../scripts/doppel.py`, relative to this skill
directory. Resolve its absolute path before running it. Use `python3` and quote
the path. The helper respects `CODEX_HOME`, otherwise `~/.codex`.

## Inspect

Run `python3 <helper> status`. Report the state, selected files, and next step.
Status reads filenames and validates file contents but does not print instructions.

## Enable

Only enable when the user asks to set up or activate Doppel.

1. Explain that setup creates a global `AGENTS.override.md` to stop automatic
   global fallback loading. Existing `AGENTS.md` and model files stay unchanged.
   Project instructions still load normally. Python 3.9+ must be available as
   `python3` to Codex, not only in an interactive shell.
2. Run status. If startup has been observed, proceed immediately. Do not ask
   for an extra session before enabling. Trusting BOTH hooks in `/hooks` before
   the first message lets the startup hook run in this session.
   If startup has not been observed, the first message has already passed
   without the hook. Ask the user to trust BOTH hooks, run `/new`, and ask for
   setup again. Do not run the hook manually or fabricate a receipt.
   A receipt only proves a past startup. Ask the user to check both hooks if
   current trust or enablement is uncertain.
3. Run `python3 <helper> enable`. Stop on an existing override conflict. Do not
   overwrite, merge, delete, or move someone else's override automatically.
4. Run status again. Report the selected filenames and tell the user to run
   `/new` once to use them. This session may already contain the fallback.

Optional files in the Codex home are `AGENTS.sol.md` for `gpt-5.6-sol` and
`AGENTS.astra.md` for `gpt-6-astra`. Missing variants use `AGENTS.md`. An existing
empty variant deliberately selects no global instruction content. Do not
rewrite or create users' instruction files unless they ask.

## Remove

Run `python3 <helper> disable` BEFORE uninstalling or disabling the plugin.
This removes only the unchanged Doppel override and preserves instruction
files. If removal refuses a changed override, explain the conflict rather than
deleting it. Then the user may remove the plugin through Codex and start a new
session. The harmless startup receipt may remain.

## Limits

Use fresh sessions and fresh-history subagents for clean model separation.
Switching models or inheriting history can carry previous instructions.
The plugin does not erase history, enforce model obedience, or control Codex's
internal system agents. Hooks must remain enabled and trusted. If they stop
running while the override exists, automatic global fallback is suppressed.
Restore it with `disable`, even if the plugin must first be reinstalled.
