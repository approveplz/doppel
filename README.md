# Doppel

Give each Codex model its own `AGENTS.md`.

[![Tests](https://github.com/approveplz/doppel/actions/workflows/test.yml/badge.svg)](https://github.com/approveplz/doppel/actions/workflows/test.yml)
[MIT](LICENSE)

Use one set of instructions for your coordinator and another for your coding
agent. Doppel picks the file for the active model, including fresh subagents.
No custom Codex build. Your project instructions still apply.

| Model | Global instructions |
| --- | --- |
| Astra (`gpt-6-astra`) | `~/.codex/AGENTS.astra.md` |
| Sol (`gpt-5.6-sol`) | `~/.codex/AGENTS.sol.md` |
| Missing model file, or any other model | `~/.codex/AGENTS.md` |

The selected file replaces the global fallback. It does not get appended to it.
Your existing `AGENTS.md` stays untouched.

## Get started

You need Codex CLI and Python 3.9+ available as `python3`. Tested with Codex
**0.153.2** on macOS and Linux. Doppel is experimental.

```sh
codex plugin marketplace add approveplz/doppel
codex plugin add doppel@doppel
codex
```

1. Before your first message, open `/hooks` and trust both Doppel hooks.
2. Ask **“Set up Doppel.”**
3. Run `/new`.

Create `AGENTS.astra.md` or `AGENTS.sol.md` in `~/.codex` with the instructions
you want that model to follow. Leave a file absent to use your existing
`AGENTS.md`. Start a new session after changing the files.

Ask **“Check Doppel status”** to see which files will load. If you use
`CODEX_HOME`, put the files there instead of `~/.codex`.

Setup creates `AGENTS.override.md` so the hook can select your global
instructions. **Disable Doppel before uninstalling it.** Setup will not
overwrite an existing override.

## Astra coordinates. Sol implements.

An Astra session can use `AGENTS.astra.md` while its Sol subagent uses
`AGENTS.sol.md`. Ask your coordinator:

> Delegate this task to a Sol subagent with `fork_turns="none"` so it starts
> without inherited conversation history.

Fresh history matters. Doppel cannot remove instructions already in a
conversation. Use new sessions after switching models, and fresh subagents
when their model differs from the coordinator's.

## Uninstall

Ask **“Disable Doppel”**, then run:

```sh
codex plugin remove doppel@doppel
```

Start a new session. Normal `AGENTS.md` loading resumes, and your instruction
files stay where they are.

## Help and contributing

[Setup help and limitations](docs/usage.md) ·
[Report a bug](https://github.com/approveplz/doppel/issues) ·
[Contribute](CONTRIBUTING.md)

The tests check the instructions sent by stock Codex, including model
selection, fallback, hook approval, and delegation. They run locally without
paid model calls.

Doppel is an independent project by [approveplz](https://github.com/approveplz),
not an official OpenAI plugin. Licensed under [MIT](LICENSE).
