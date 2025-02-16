# gpt-epub-rename

This is a demo Python script that shows how to use ChatGPT's python API to
rename downloaded EPUB files.

## Installation

I am no expert with Python script setups, but the following should work:

```shell
python3 -m venv .
source bin/activate
pip install openai
```

You also need an OpenAI API key. You can either directly put it in
`~/.gpt_apikey`, otherwise the script will ask you for it and give you the
option to create this file.

## Usage

```shell
python3 rename.py download_dir
```

where `download_dir` is the location of EPUB directories to rename.
