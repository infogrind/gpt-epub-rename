# LLM-based Renamer for EPUB Files

## Purpose

Downloaded EPUB files are often badly named. The purpose of this tool is, based
on the download name, to properly rename a file into its correct format. Each EPUB
file should be put into a directory.

## Development

Run tests:

```sh
uv run pytest
```

Lint:

```sh
ruff check
```

The main code is in rename.py, tests are in the tests/ subdirectory.
