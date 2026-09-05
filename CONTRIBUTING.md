# Contributing

Bug reports, small fixes, and clearer docs are welcome. For changes to file
selection or setup behavior, open an issue first so we can agree on the scope.

Include your OS, Codex version, steps to reproduce, and what you expected.
Do not post credentials or private instruction contents.

## Run the tests

From the repository root:

```sh
python3 -m unittest discover -s tests -v
```

To also test against stock Codex:

```sh
DOPPEL_CODEX="$(command -v codex)" python3 -m unittest discover -s tests -v
```

The integration tests install the plugin in temporary Codex homes and capture
requests with a local mock model server. No API key or paid inference is
needed. The onboarding test uses the same approval requests as `/hooks`.
Other integration tests bypass hook trust only within their temporary homes.

To test the published plugin instead of the local checkout:

```sh
DOPPEL_CODEX="$(command -v codex)" DOPPEL_MARKETPLACE=approveplz/doppel python3 -m unittest discover -s tests -v
```

CI runs unit tests on Python 3.9 and 3.13, plus integration tests against
Codex CLI 0.153.2. Formatting and lint use Ruff 0.12.12:

```sh
ruff check .
ruff format --check .
```

## Try a local change

Use a separate `CODEX_HOME` if you do not want to change your normal setup.
Register the absolute path to your checkout with
`codex plugin marketplace add /path/to/doppel`, then install `doppel@doppel`.
Follow the README setup steps in a new Codex session.
