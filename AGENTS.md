# AGENTS.md

Guidance for AI coding agents working in this repository.

## Purpose

CLI tool that renames badly-named downloaded EPUB files/directories into a
standardized `Lastname - Title (year)` format, using the OpenAI API
(gpt-4o-mini) to extract author/title from the original names. Each EPUB file
ends up inside its own directory.

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

Requires Python 3.13+ (managed via `uv`). An OpenAI API key is read from
`~/.gpt_apikey` (the script prompts if missing).

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
  (no file extension in suggestions).
- Module-level globals `client` (OpenAI, initialized in `main()`) and `debug`
  are used throughout; tests rely on patching `rename.OpenAI` and
  `rename.load_api_key`.

Tests (`tests/test_rename.py`, unittest-style) invoke `main()` with a patched
`sys.argv`, mock the OpenAI client response, and assert on captured stdout — no
real API calls.
