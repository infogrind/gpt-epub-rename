import argparse
import json
import os
import sys
import tomllib

import anthropic
import openai
from anthropic import Anthropic
from openai import OpenAI

CONFIG_FILE = os.path.expanduser("~/.config/gpt-epub-rename/config.toml")
LEGACY_OPENAI_KEY_FILE = os.path.expanduser("~/.gpt_apikey")

DEFAULT_CONFIG = """\
# Configuration for gpt-epub-rename.
#
# provider: which LLM API to use for renaming suggestions.
#   "anthropic" — Claude via the Anthropic API
#   "openai"    — ChatGPT via the OpenAI API
provider = "anthropic"

[anthropic]
model = "claude-opus-4-8"
# The API key is resolved in this order:
#   1. api_key below
#   2. the file named by api_key_file
#   3. the ANTHROPIC_API_KEY environment variable, or an `ant auth login` profile
# api_key = "sk-ant-..."
# api_key_file = "~/.anthropic_apikey"

[openai]
model = "gpt-4o-mini"
# Key resolution: api_key, then api_key_file, then the OPENAI_API_KEY
# environment variable, then an interactive prompt.
api_key_file = "~/.gpt_apikey"
"""

debug = False  # Global debug flag

# Set in main() from the config file
provider = None
client = None
model = None


def debug_print(message):
    """Print debug information to stderr if debug mode is enabled."""
    if debug:
        print(f"🔧 DEBUG: {message}", file=sys.stderr)


def load_config():
    """Loads the TOML config, creating a commented default on first run."""
    if not os.path.exists(CONFIG_FILE):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            f.write(DEFAULT_CONFIG)
        print(
            f"📝 Created default config at {CONFIG_FILE} — "
            "edit it to change the provider or model."
        )
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def read_key_file(path):
    """Returns the stripped contents of a key file, or None if unset/missing."""
    if not path:
        return None
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return f.read().strip()


def load_api_key():
    """Legacy OpenAI flow: read ~/.gpt_apikey, or prompt the user."""
    key = read_key_file(LEGACY_OPENAI_KEY_FILE)
    if key:
        return key

    print(f"⚠️ API key file '{LEGACY_OPENAI_KEY_FILE}' not found.")
    api_key = input("Enter your OpenAI API key: ").strip()

    save_choice = (
        input("Save this key to ~/.gpt_apikey for future use? (y/N):").strip().lower()
    )
    if save_choice == "y":
        with open(LEGACY_OPENAI_KEY_FILE, "w") as f:
            f.write(api_key)
            print(f"✅ API key saved to {LEGACY_OPENAI_KEY_FILE}")

    return api_key


def create_client(config):
    """Creates the LLM client for the configured provider.

    Returns a (provider, client, model) tuple.
    """
    chosen = config.get("provider", "anthropic")
    section = config.get(chosen, {})
    api_key = section.get("api_key") or read_key_file(section.get("api_key_file"))

    if chosen == "anthropic":
        chosen_model = section.get("model", "claude-opus-4-8")
        # With no explicit key the SDK resolves ANTHROPIC_API_KEY or an
        # `ant auth login` profile on its own.
        llm = Anthropic(api_key=api_key) if api_key else Anthropic()
    elif chosen == "openai":
        chosen_model = section.get("model", "gpt-4o-mini")
        if not api_key and not os.environ.get("OPENAI_API_KEY"):
            api_key = load_api_key()
        llm = OpenAI(api_key=api_key) if api_key else OpenAI()
    else:
        print(
            f"❌ Error: unknown provider '{chosen}' in {CONFIG_FILE} "
            '(expected "anthropic" or "openai").'
        )
        sys.exit(1)

    debug_print(f"Using provider '{chosen}' with model '{chosen_model}'")
    return chosen, llm, chosen_model


def auth_error(detail):
    """Prints a friendly authentication error and exits."""
    print(f"❌ Authentication with the {provider} API failed: {detail}", file=sys.stderr)
    print(
        f"   Set api_key or api_key_file in the [{provider}] section of "
        f"{CONFIG_FILE}, or export the provider's API key environment variable.",
        file=sys.stderr,
    )
    sys.exit(1)


def api_error(detail):
    """Prints a friendly API error and exits."""
    print(f"❌ The {provider} API returned an error: {detail}", file=sys.stderr)
    sys.exit(1)


def query_model(prompt):
    """Sends the prompt to the configured provider and returns the text reply."""
    if provider == "anthropic":
        try:
            response = client.messages.create(
                model=model,
                max_tokens=16000,
                messages=[{"role": "user", "content": prompt}],
            )
        except TypeError as e:
            # The SDK raises TypeError when no credentials can be resolved
            if "authentication" in str(e).lower():
                auth_error("no API key found")
            raise
        except anthropic.AuthenticationError as e:
            auth_error(e.message)
        except anthropic.APIConnectionError:
            api_error("could not connect — check your network")
        except anthropic.APIStatusError as e:
            api_error(e.message)
        if response.stop_reason == "refusal":
            raise RuntimeError("The model refused to answer the request")
        text = "".join(b.text for b in response.content if b.type == "text")
    else:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
            )
        except openai.AuthenticationError as e:
            auth_error(getattr(e, "message", str(e)))
        except openai.APIConnectionError:
            api_error("could not connect — check your network")
        except openai.APIStatusError as e:
            api_error(getattr(e, "message", str(e)))
        text = response.choices[0].message.content
        if text is None:
            raise TypeError("No text content found in OpenAI response")
    return text.strip()


def parse_json_reply(text):
    """Parses a JSON reply, tolerating a markdown code fence around it."""
    if text.startswith("```"):
        first_newline = text.index("\n") if "\n" in text else len(text)
        text = text[first_newline + 1 :]
        text = text.rstrip().removesuffix("```").rstrip()
    return json.loads(text)


def get_renaming_suggestions(item_names):
    """Queries the configured LLM to get structured renaming suggestions."""

    debug_print(f"Preparing to query the {provider} API for {len(item_names)} items")
    prompt = f"""This is a list of names of directories or EPUB files.
The goal is to rename them into a standardized structure. Each
name normally contains a title and its author, along with unimportant
terms like epub or xpost or retail. Please extract the author and title from
each line, and return in structured JSON format instructions that my script can
use for renaming. The JSON should contain a list where each element is a list with two elements, where
the first element has the original name and the second field has
the form "Lastname - Title (year)", where "Lastname" is the last name of the author.
Do NOT include a file extension in the suggested name.

Example: if the single input is
"Jill_Lepore_-_These_Truths_-_A_History_of_The_United_States_(retail)_(epub)",
the JSON output should be:

  [
    [
      "Jill_Lepore_-_These_Truths_-_A_History_of_The_United_States_(retail)_(epub)",
      "Lepore - These Truths - A History of the United States (2018)"
    ],
  ]

Here 2018 is the year where the book was published. It is not in the
original string, but perhaps you know the information.

If the book title contains a colon, like "These Truths: A History of the United
States", then replace it with a dash, as in "These Truths - A History of the
United States".

If there are two authors, write both of their last names, separated with a
comma. If there are more than two, only keep the first author's last name
followed by "et al.", for example "Parshall et al. - Shattered Sword - The
Untold Story of the Battle of Midway".

Here are the names: {json.dumps(item_names, indent=2)}

Return only a JSON list of tuples without any extra text or markdown."""

    debug_print(f"Sending request to the {provider} API")
    response_text = query_model(prompt)
    debug_print(f"Received response: {len(response_text)} characters")
    debug_print(f"Response contents: {response_text}")

    try:
        result = parse_json_reply(response_text)
        debug_print(
            f"Successfully parsed JSON response with {len(result)} rename suggestions"
        )
        return result
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing API response: {e}", file=sys.stderr)
        debug_print(f"Raw API response: {response_text}")
        raise


def rename_items(items, dry_run=False):
    """Processes directories and EPUB files, and renames them according to LLM suggestions."""
    debug_print(f"Total items to process: {len(items)}")
    # Remove trailing slashes to ensure os.path.basename returns the name
    items = [i.rstrip(os.sep) for i in items]
    old_names = [os.path.basename(i) for i in items]
    debug_print(f"Extracted {len(old_names)} item basenames")
    rename_pairs = get_renaming_suggestions(old_names)

    debug_print(f"Processing {len(rename_pairs)} rename pairs")
    for old_name, new_name in rename_pairs:
        debug_print(f"Processing rename: {old_name} → {new_name}")
        old_path = next((i for i in items if os.path.basename(i) == old_name), None)
        if not old_path:
            print(f"⚠️ Skipping: {old_name} (not found)")
            continue

        base_dir = os.path.dirname(old_path)
        new_path = os.path.join(base_dir, new_name)

        if os.path.isfile(old_path) and old_path.lower().endswith(".epub"):
            # If it's an EPUB file, we create a directory and move the file into it
            new_file_path = os.path.join(new_path, new_name + ".epub")
            debug_print(f"File move: {old_path} → {new_file_path}")

            if os.path.exists(new_path):
                print(f"⚠️ Skipping: {old_name} → {new_name} (target directory already exists)")
                continue

            if dry_run:
                print(f"🔍 Dry Run: {old_name} → {new_name}/{new_name}.epub")
            else:
                os.makedirs(new_path)
                os.rename(old_path, new_file_path)
                print(f"✅ Renamed and moved: {old_name} → {new_name}/{new_name}.epub")
        else:
            # If it's a directory, we just rename it
            debug_print(f"Directory rename: {old_path} → {new_path}")

            if os.path.exists(new_path):
                print(f"⚠️ Skipping: {old_name} → {new_name} (target already exists)")
                continue

            if dry_run:
                print(f"🔍 Dry Run: {old_name} → {new_name}")
            else:
                os.rename(old_path, new_path)
                print(f"✅ Renamed: {old_name} → {new_name}")


def main():
    parser = argparse.ArgumentParser(
        description="Rename EPUB directories into a standardized format using an LLM."
    )
    parser.add_argument(
        "directories",
        nargs="*",
        default=[],
        help="One or more directories to rename.",
    )
    parser.add_argument(
        "-d",
        "--directory",
        dest="parent_directory",
        help="A directory containing subdirectories to rename.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview renaming without making changes.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with detailed logging to stderr.",
    )

    args = parser.parse_args()
    global debug
    debug = args.debug

    if debug:
        print(
            "🔧 Debug mode enabled - detailed information will be printed to stderr",
            file=sys.stderr,
        )

    global provider, client, model
    provider, client, model = create_client(load_config())

    items_to_rename = []
    if args.parent_directory:
        if not os.path.exists(args.parent_directory):
            print(f"❌ Error: Directory '{args.parent_directory}' not found.")
            sys.exit(1)
        if not os.path.isdir(args.parent_directory):
            print(
                f"❌ Error: '{args.parent_directory}' exists but is not a directory."
            )
            sys.exit(1)

        for d in os.listdir(args.parent_directory):
            full_path = os.path.join(args.parent_directory, d)
            if os.path.isdir(full_path):
                items_to_rename.append(full_path)
            elif os.path.isfile(full_path) and full_path.lower().endswith(".epub"):
                items_to_rename.append(full_path)

    for item in args.directories:
        if os.path.isdir(item):
            items_to_rename.append(item)
        elif os.path.isfile(item) and item.lower().endswith(".epub"):
            items_to_rename.append(item)
        else:
            print(f"Skipping: {item} (not a directory or EPUB file)")

    if not items_to_rename:
        print("❌ No valid directories or EPUB files found to rename.")
        sys.exit(1)

    rename_items(items_to_rename, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
