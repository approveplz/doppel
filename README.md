# Doppel

Different models. Their own instructions.

Give Sol and Astra different global instructions in Codex. Each model gets its
own file when present, otherwise it gets your existing `AGENTS.md`.

[![Tests](https://github.com/approveplz/doppel/actions/workflows/test.yml/badge.svg)](https://github.com/approveplz/doppel/actions/workflows/test.yml)
[Experimental release](https://github.com/approveplz/doppel/releases/tag/v0.2.0) · [MIT license](LICENSE)

| Model | Instructions |
| --- | --- |
| `gpt-5.6-sol` | `~/.codex/AGENTS.sol.md` |
| `gpt-6-astra` | `~/.codex/AGENTS.astra.md` |

Missing model files and all other models use `~/.codex/AGENTS.md`. Files replace
the fallback, not add to it. An empty model file selects no global instruction
content. If you use `CODEX_HOME`, put the files there instead.

This works with unmodified Codex. Project instructions still load normally.
Use new sessions and subagents without inherited history. The plugin cannot
remove instructions already in a conversation.

## Install

Tested with Codex CLI **0.153.2** on **macOS and Linux**. Codex must be able to
run **Python 3.9+** as `python3`. Windows, remote executor setups, and desktop
app behavior have not been verified.

**Before installing:** setup creates a global `AGENTS.override.md`. While that
file exists, Codex relies on this plugin for global instructions. Disable the
loader before uninstalling the plugin. Setup refuses to overwrite an existing
override.

Previously installed **Model Agents**? Follow [the migration steps](#migrating-from-model-agents)
before installing Doppel.

```sh
codex plugin marketplace add approveplz/doppel
codex plugin add doppel@doppel
```

1. Open Codex CLI. **Before sending your first message**, open `/hooks` and
   review and trust both Doppel hooks.
2. In that same session, ask **“Set up Doppel.”**
3. Run `/new`. Your selected instructions now apply.

Already sent a message before trusting the hooks? Trust them, then run `/new`
before asking for setup. The startup hook must run before setup can enable the
loader. Ask **“Check Doppel status”** whenever you need the selected
filenames or the next setup step.

Add `AGENTS.sol.md` or `AGENTS.astra.md` when you want different instructions.
Setup does not create these files or change your existing `AGENTS.md`.

## Subagents and model changes

An Astra coordinator can use `AGENTS.astra.md` while a Sol child uses
`AGENTS.sol.md`. Spawn the child with `fork_turns="none"` so it does not inherit
the coordinator's instruction history.

Start a new session after changing models or editing instruction files. The
plugin does not reload them on every turn. After updates, review any changed
hooks in `/hooks` and start a new session.

## Migrating from Model Agents

Ask Codex to **“Disable Model Agents”** while the old plugin is still installed.
Then remove it and its marketplace:

```sh
codex plugin remove model-agents@model-agents
codex plugin marketplace remove model-agents
```

Follow the Doppel install steps above. Your `AGENTS.md`, `AGENTS.sol.md`, and
`AGENTS.astra.md` files do not need changes. Doppel will not overwrite the old
loader's `AGENTS.override.md`, so disable the old loader first.

If you already removed the old plugin, its [v0.1.0 release](https://github.com/approveplz/doppel/releases/tag/v0.1.0)
is still available. Reinstall it from that tag to disable the old loader:

```sh
codex plugin marketplace add approveplz/doppel --ref v0.1.0
codex plugin add model-agents@model-agents
```

## Disable or uninstall

Ask Codex to **“Disable Doppel” first**, then remove the plugin:

```sh
codex plugin remove doppel@doppel
```

Start a new session to restore normal `AGENTS.md` loading. Your instruction
files stay untouched. The helper removes only the unchanged override it created.

If you already removed the plugin, reinstall it and ask Codex to disable it.
If you edited the override, the helper refuses to remove it. Review that file
yourself so you do not lose your changes.

<details>
<summary>Run setup commands directly</summary>

Find the installed plugin path with `codex plugin list --json`, then run:

```sh
python3 /path/to/plugin/scripts/doppel.py status
python3 /path/to/plugin/scripts/doppel.py enable
python3 /path/to/plugin/scripts/doppel.py disable
```

Choose the command you need. Enabling still requires a startup hook receipt.
The receipt at `doppel/startup.json` records a past execution of this
plugin version, not whether its hooks remain trusted or enabled. Removal leaves
that small file behind.

</details>

## How it works

Codex prefers global `AGENTS.override.md` over `AGENTS.md`. This plugin keeps
a fixed override and uses `SessionStart` and `SubagentStart` hooks to read the
file for the active model. Sessions never swap or rewrite shared instruction
files.

Hooks add developer context rather than native AGENTS messages. The plugin
tells the model to defer to project instructions on conflicts, but it does not
reproduce Codex's native instruction handling exactly or guarantee obedience.

If hooks stop running, the override still prevents automatic fallback loading.
It tells the agent to report missing instructions, but cannot enforce a stop.
Run `disable` to restore the fallback. Codex's internal system agents are not
covered.

Files must be UTF-8 and at most 64 KiB. A file that cannot be read or exceeds
that limit causes an error, not a silent fallback. The plugin makes no network
requests and collects no telemetry. Selected instructions are sent as part of
your normal Codex model request.

## Bugs and contributions

[Open an issue](https://github.com/approveplz/doppel/issues) with your OS,
Codex version, steps to reproduce, and expected result. Include the selected
filename if relevant. Do not post credentials or private instruction content.

Small fixes, clearer docs, and reproducible compatibility reports are welcome.
For changes to file selection or setup, describe the proposed behavior in an
issue first.

To test a change:

```sh
python3 -m unittest discover -s tests -v
DOPPEL_CODEX="$(command -v codex)" python3 -m unittest discover -s tests -v
```

The second command also tests stock Codex against a local mock model server.
It checks the instructions actually sent, including fallback selection, safe
removal, hook approval, and Sol delegation from Astra. The onboarding test uses
the same approval requests as `/hooks` and verifies setup needs only one new
session. Tests use temporary Codex homes and no paid model calls. Other tests
bypass hook approval only inside their temporary homes.

For local plugin development, replace the GitHub source in the install command
with the absolute path to your checkout.

To test the public download instead of local source:

```sh
DOPPEL_CODEX="$(command -v codex)" DOPPEL_MARKETPLACE=approveplz/doppel python3 -m unittest discover -s tests -v
```

## References

[Codex instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md#how-codex-discovers-guidance) ·
[Hooks](https://learn.chatgpt.com/docs/hooks) ·
[Plugin installation](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli)

Maintained by [approveplz](https://github.com/approveplz).
Independent project, not an official OpenAI plugin.
