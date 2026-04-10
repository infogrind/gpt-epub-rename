import os
import json
import argparse
import sys
from openai import OpenAI

API_KEY_FILE = os.path.expanduser(
    "~/.gpt_apikey"
)  # API key stored in the user's home directory
debug = False  # Global debug flag


def load_api_key():
    """Loads the API key from ~/.gpt_apikey, or prompts the user if missing."""
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, "r") as f:
            return f.read().strip()

    print(f"⚠️ API key file '{API_KEY_FILE}' not found.")
    api_key = input("Enter your OpenAI API key: ").strip()

    save_choice = (
        input("Save this key to ~/.gpt_apikey for future use? (y/N):").strip().lower()
    )
    if save_choice == "y":
        with open(API_KEY_FILE, "w") as f:
            f.write(api_key)
            print(f"✅ API key saved to {API_KEY_FILE}")

    return api_key


client = None  # Will be initialized in main()


def debug_print(message):
    """Print debug information to stderr if debug mode is enabled."""
    if debug:
        print(f"🔧 DEBUG: {message}", file=sys.stderr)


def get_renaming_suggestions(item_names):
    """Queries ChatGPT to get structured renaming suggestions."""

    debug_print(f"Preparing to query OpenAI API for {len(item_names)} items")
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

    debug_print("Sending request to OpenAI API")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    )

    response_content = response.choices[0].message.content
    if response_content is None:
        raise TypeError("No text content found in OpenAI response")

    response_text = response_content.strip()
    debug_print(f"Received response from OpenAI API: {len(response_text)} characters")
    debug_print(f"Response contents: {response_text}")

    try:
        result = json.loads(response_text)
        debug_print(
            f"Successfully parsed JSON response with {len(result)} rename suggestions"
        )
        return result
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing API response: {e}", file=sys.stderr)
        debug_print(f"Raw API response: {response_text}")
        raise


def rename_items(items, dry_run=False):
    """Processes directories and EPUB files, and renames them according to ChatGPT suggestions."""
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
        description="Rename EPUB directories into a standardized format using ChatGPT."
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

    global client
    client = OpenAI(api_key=load_api_key())

    if debug:
        print(
            "🔧 Debug mode enabled - detailed information will be printed to stderr",
            file=sys.stderr,
        )

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
