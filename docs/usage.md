# Using Doppel

## Setup help

**Setup asks for hook approval?** Open `codex`, use `/hooks` to enable and trust
both Doppel hooks, then `/quit`. Rerun `./doppel setup` in your terminal. You do
not need to send a message. Setup checks current trust through Codex's local
app-server, without opening a model session or granting trust itself.

**Already have an `AGENTS.override.md`?** Doppel refuses to replace it. If
another loader owns it, disable that loader first. If it contains your own
instructions, review where you want those instructions to live before moving
or changing it.

**Instructions missing?** Check that both hooks are enabled and trusted in
`/hooks`, and that `python3` is available to Codex. Run `./doppel status`.
After updating the plugin, review any changed hooks and start a new session.

**Removed the plugin before disabling it?** Run `./doppel disable`. The script
does not need the plugin installed to restore normal loading. It removes only
its own unchanged override. If you edited the
override, review it yourself before removing anything.

## Commands

The download is a standalone Python script, also bundled in the plugin. No
Python packages are required. You can run it with `python3 doppel` if you do
not want to make it executable.

```sh
./doppel setup
./doppel status
./doppel disable
./doppel uninstall
```

Setup registers the marketplace, installs the plugin, checks that both hooks
are enabled and trusted, and creates the loader override. It is safe to rerun.
During updates, setup pauses the loader until the new installation passes
these checks. Normal fallback loading stays available while approval is pending.
It never rewrites instruction files. Uninstall disables the loader before
removing the plugin. It leaves the marketplace registration available.

The script uses `CODEX_HOME`, or `~/.codex` when unset. Management commands
also accept `--home /path/to/test-home`. Status prints selected filenames,
the loader state, and the next setup step, not your instruction contents.

For an already installed plugin, `./doppel enable` checks trust and activates
without reinstalling. `./doppel setup --source /path/to/doppel` installs from
a local checkout. Set `DOPPEL_CODEX` to use a specific Codex executable.

## File selection

Doppel maps `gpt-6-astra` to `AGENTS.astra.md`, `gpt-5.6-sol` to `AGENTS.sol.md`,
`gpt-5.6-luna` to `AGENTS.luna.md`, and `gpt-5.6-terra` to `AGENTS.terra.md`.
A missing variant falls back to `AGENTS.md`. Other models also use `AGENTS.md`.

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

Doppel's hooks make no network requests and collect no telemetry. Setup uses
the Codex CLI to download the plugin from GitHub. Your selected instructions
are included in normal Codex model requests.

## Codex references

- [Instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md#how-codex-discovers-guidance)
- [Hooks and trust](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)
- [Plugin installation](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli)
