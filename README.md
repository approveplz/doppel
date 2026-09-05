# Model Agents

Global instructions for each Codex model. Keep `AGENTS.md` as the fallback.
Runs on stock Codex. No fork, model API key, or third-party Python packages.

| Active model | First choice | If missing |
| --- | --- | --- |
| `gpt-5.6-sol` | `AGENTS.sol.md` | `AGENTS.md` |
| `gpt-6-astra` | `AGENTS.astra.md` | `AGENTS.md` |
| Other models | `AGENTS.md` | No global instructions |

All files live in your Codex home, usually `~/.codex`. `CODEX_HOME` is respected.
Only one instruction file is selected. An existing empty model file intentionally
selects no global instruction content. Filenames and model slugs are exact.

## Install

Requires Codex with plugin marketplaces and `SessionStart` / `SubagentStart`
hooks that report the active model. Tested with **Codex CLI 0.153.2**.
Python **3.9+** must be available to Codex as `python3`. macOS and Linux are the
initial supported platforms. Windows is not supported by the bundled command.

Add the public marketplace and install the plugin:

```sh
codex plugin marketplace add approveplz/model-agents
codex plugin add model-agents@model-agents
```

1. Open Codex CLI and use `/hooks` to review and trust **both** Model Agents
   hooks. Do not bypass hook trust for normal use.
2. Start a new session and ask: **Set up Model Agents.** The included setup
   skill checks the startup receipt and activates the loader.
3. Start another new session. It now uses the selected file. Existing sessions
   may already contain the old fallback instructions.

Add `AGENTS.sol.md` or `AGENTS.astra.md` whenever you want a replacement. Your
existing `AGENTS.md` is neither renamed nor edited. Project instructions are
outside this plugin's scope and continue to load normally.

The plugin also appears in the desktop app's plugin catalog after adding the
marketplace. The documented setup uses CLI hook approval. Desktop behavior has
not been independently tested.

## Status and removal

Ask Codex to **check Model Agents status** or **disable Model Agents**. Its setup
skill runs the bundled helper. To run it directly, locate the installed plugin
with `codex plugin list --json`, then use its `scripts/model_agents.py`:

```sh
python3 /path/to/plugin/scripts/model_agents.py status
python3 /path/to/plugin/scripts/model_agents.py disable
```

Disable the loader **before** removing the plugin:

```sh
codex plugin remove model-agents@model-agents
```

Start a new session to restore ordinary `AGENTS.md` loading. Removal preserves
all your instruction files and removes only the unchanged override created by
Model Agents. It leaves a harmless startup receipt in `model-agents/startup.json`.

If the plugin has already been removed, reinstall it to run `disable`. If you
edited its override, the helper refuses to remove it. Inspect and resolve that
file yourself rather than discarding your changes.

## How it works

Codex automatically loads global `AGENTS.override.md` **instead of** `AGENTS.md`.
Setup creates a small override telling the agent that a hook supplies its global
instructions. The hook receives the actual model and injects the corresponding
file, or the original `AGENTS.md` when no variant exists.

The override stays constant. Concurrent Astra and Sol sessions never swap or
rewrite shared instruction files. Setup refuses existing overrides, including
symlinks. It requires evidence that this version's startup hook has executed.
That receipt proves a past execution, not ongoing trust or enablement.

Instruction files are UTF-8 and capped at 64 KiB each. Oversized or unreadable
selected files produce a hook error instead of silently selecting a different
file. Hook output is bounded here and delivered without Codex's usual preview
truncation. The plugin performs no network requests and sends no telemetry.
Selected instructions become part of the normal Codex model request.

## Limits worth knowing

- **Fresh history:** Astra coordinators and fresh-history Sol subagents select
  independently. Explicitly request `fork_turns="none"` for clean separation.
  Forked or resumed history can retain previously injected instructions.
- **Model changes:** Start a new session after switching models or editing
  instructions. This version does not reload on every turn or tool call.
- **Hooks must stay on:** Disabling, untrusting, or removing the plugin while its
  override remains suppresses automatic global fallback. The override tells the
  agent to report missing context, but that is a prompt, not an enforcement gate.
  Run `disable` to recover.
- **Prompt role:** Hooks inject developer context, not native AGENTS messages.
  The wrapper explicitly defers to project instructions on conflicts, but this
  is not an exact replacement of Codex's native instruction machinery.
- **Scope:** Only global instructions and ordinary spawned subagents are handled.
  Codex's internal system agents and remote executor setups are not covered.
- **Updates:** Changed hooks need trust review again. Use status and start a new
  session after upgrading. Disable the loader first if an update breaks hooks.

## Development

The plugin has one Python module and no third-party runtime dependencies.
For a local checkout, use `codex plugin marketplace add /absolute/path/to/model-agents`
instead of the GitHub source.

```sh
python3 -m unittest discover -s tests -v
MODEL_AGENTS_CODEX="$(command -v codex)" python3 -m unittest discover -s tests -v
```

The second command also installs the plugin into temporary Codex homes and runs
stock Codex against a local mock Responses server. It checks actual outbound
instruction content, fallback suppression, restoration, trust gating, and fresh
Sol delegation from Astra. No paid inference or API credentials are needed.
The test harness explicitly bypasses hook trust only for its own fixture plugin.
It does not change the user's real Codex home or install a global override.

These tests prove loading behavior, not live-model obedience.

## References

- [Codex AGENTS discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md#how-codex-discovers-guidance)
- [Codex hooks](https://learn.chatgpt.com/docs/hooks)
- [Plugin marketplaces](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli)

MIT licensed. Independent project, not an official OpenAI plugin.
