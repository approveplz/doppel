# Using Doppel

## Setup help

**Sent a message before trusting the hooks?** Open `/hooks`, trust both Doppel
hooks, then run `/new` and ask to set up Doppel again. Setup waits for a real
startup hook before enabling the loader.

**Already have an `AGENTS.override.md`?** Doppel refuses to replace it. If
another loader owns it, disable that loader first. If it contains your own
instructions, review where you want those instructions to live before moving
or changing it.

**Instructions missing?** Check that both hooks are enabled and trusted in
`/hooks`, and that `python3` is available to Codex. Ask to check Doppel status.
After updating the plugin, review any changed hooks and start a new session.

**Removed the plugin before disabling it?** Reinstall Doppel and ask to disable
it. The helper removes only its own unchanged override. If you edited the
override, review it yourself before removing anything.

## Run the helper directly

Use `codex plugin list --json` to find Doppel's installed path, then choose
the command you need:

```sh
python3 /path/to/doppel/scripts/doppel.py status
python3 /path/to/doppel/scripts/doppel.py enable
python3 /path/to/doppel/scripts/doppel.py disable
```

The helper uses `CODEX_HOME`, or `~/.codex` when unset. Management commands
also accept `--home /path/to/test-home`. Status prints selected filenames,
the loader state, and the next setup step, not your instruction contents.

Enabling requires a startup receipt for the installed helper. The receipt at
`doppel/startup.json` proves a past startup, not that hooks remain trusted or
enabled. Disabling leaves the receipt behind.

## File selection

Doppel reads `AGENTS.astra.md` for `gpt-6-astra` and `AGENTS.sol.md` for
`gpt-5.6-sol`. A missing variant falls back to `AGENTS.md`. Other models also
use `AGENTS.md`. These are the two model mappings currently supported.

An existing empty variant deliberately selects no global instruction content.
Files must be UTF-8 and at most 64 KiB. Unreadable or oversized files cause an
error rather than silently selecting the fallback.

Instructions load at agent startup, not on every turn. Start a new session
after changing models or editing files.

## How it works and limits

Codex prefers global `AGENTS.override.md` over `AGENTS.md`. Doppel creates a
fixed override, then uses `SessionStart` and `SubagentStart` hooks to read the
selected file. Concurrent sessions never swap shared files on disk. Project
instructions continue to load normally.

Hooks inject developer context, not native AGENTS messages. Doppel tells the
model to defer to project instructions on conflicts, but this is not identical
to native instruction precedence. It does not guarantee model obedience.

The override remains if hooks stop running. In that state, Codex will not
automatically load your fallback. The override asks the agent to report the
problem, but cannot enforce a stop. Run `disable` to restore native loading.

Use fresh sessions and subagents without inherited history for separate model
instructions. Existing conversation history may contain another model's
instructions. Codex's internal system agents do not receive these startup
hooks and are not covered.

Tested on macOS and Linux with Codex CLI 0.153.2. Windows, the desktop app, and
remote executor setups have not been verified.

Doppel makes no network requests and collects no telemetry. Your selected
instructions are included in normal Codex model requests.

## Codex references

- [Instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md#how-codex-discovers-guidance)
- [Hooks and trust](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)
- [Plugin installation](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli)
