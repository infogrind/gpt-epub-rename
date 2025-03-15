# gpt-epub-rename

This is a demo Python script that shows how to use ChatGPT's python API to
rename downloaded EPUB files.

## Requirements

You need an OpenAI API key. You can either directly put it in `~/.gpt_apikey`,
otherwise the script will ask you for it and give you the option to create this
file.

The recommended way to run the script is using `uv` (https://github.com/astral-sh/uv).

## Usage

```shell
uv run -s rename.py download_dir
```

where `download_dir` is the location of EPUB directories to rename.
