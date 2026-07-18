# AGENTS.md

Guidance for AI coding agents working in this repository.

## Purpose

CLI tool that renames badly-named downloaded EPUB files/directories into a
standardized `Lastname - Title (year)` format, using an LLM (Anthropic Claude
or OpenAI ChatGPT) to extract author/title from the original names. Each EPUB
file ends up inside its own directory.

## Commands

```sh
# Run all tests
uv run pytest
# Run a single test
uv run pytest \
  tests/test_rename.py::TestRenameScript::test_rename_with_d_option
# lint
ruff check
# run the tool (dry run)
uv run -s rename.py <dir> --dry-run
```

Requires Python 3.13+ (managed via `uv`).

## Configuration

`~/.config/gpt-epub-rename/config.toml` (a commented template is auto-created
on first run, defaulting to Anthropic with `claude-opus-4-8`). It selects the
`provider` (`"anthropic"` or `"openai"`) and, per provider, `model`, `api_key`,
and `api_key_file`. If no key is configured, Anthropic falls back to the SDK's
own resolution (`ANTHROPIC_API_KEY`, `ant auth login` profile); OpenAI falls
back to `OPENAI_API_KEY`, then the legacy `~/.gpt_apikey` interactive prompt.

## Architecture

All logic lives in `rename.py` (single module, also exposed as the
`gpt-epub-rename` script entry point):

- `main()` parses args: positional paths (directories or `.epub` files) and/or
  `-d <parent>` which expands to that parent's subdirectories and EPUB files.
  `--dry-run` and `--debug` flags.
- `rename_items()` strips trailing slashes, sends the basenames to the API via
  `get_renaming_suggestions()`, then applies each `[old_name, new_name]` pair.
  Directories are renamed in place; standalone `.epub` files are moved into a
  newly created directory of the same new name (`New Name/New Name.epub`).
  Existing targets are skipped, never overwritten.
- `get_renaming_suggestions()` builds a single prompt containing all names and
  expects the model to return a bare JSON list of `[original, suggested]` pairs
  (no file extension in suggestions; a markdown code fence around the JSON is
  tolerated).
- `query_model()` is the only provider-specific code path (Anthropic Messages
  API vs OpenAI chat completions). Module-level globals `provider`, `client`,
  `model` (set in `main()` via `load_config()` + `create_client()`) and `debug`
  are used throughout; tests rely on patching `rename.load_config` plus
  `rename.OpenAI` / `rename.Anthropic`.

Tests (`tests/test_rename.py`, unittest-style) invoke `main()` with a patched
`sys.argv`, mock the provider client response, and assert on captured stdout —
no real API calls.
