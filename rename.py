import os
import json
import argparse
from openai import OpenAI

API_KEY_FILE = os.path.expanduser("~/.gpt_apikey")  # API key stored in the user's home directory

def load_api_key():
    """Loads the API key from ~/.gpt_apikey, or prompts the user if missing."""
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, "r") as f:
            return f.read().strip()

    print(f"⚠️ API key file '{API_KEY_FILE}' not found.")
    api_key = input("Enter your OpenAI API key: ").strip()

    save_choice = input("Save this key to ~/.gpt_apikey for future use? (y/N):"
                        ).strip().lower()
    if save_choice == "y":
        with open(API_KEY_FILE, "w") as f:
            f.write(api_key)
            print(f"✅ API key saved to {API_KEY_FILE}")

    return api_key

client = OpenAI(api_key=load_api_key())

def get_renamed_directories(directory_names):
    """Queries ChatGPT to get structured renaming suggestions."""

    prompt = f"""This is a list of names of directories containing EPUB files.
The goal is to rename the directories into a standardized structure. Each
directory name normally contains a title and its author, along with unimportant
terms like epub or xpost or retail. Please extract the author and title from
each line, and return in structured JSON format instructions that my script can
use for renaming. The JSON should contain a list where each element is a list with two elements, where
the first element has the original directory name and the second field has
the form "Lastname - Title (year)", where "Lastname" is the last name of the author.

Example: if the single input is
"Jill_Lepore_-_These_Truths_-_A_History_of_The_United_States_(retail)_(epub)",
the JSON output should be:

  [ 
    [
      "Jill_Lepore_-_These_Truths_-_A_History_of_The_United_States_(retail)_(epub)",
      "Lepore - These Truths - A Hoistory of the United States (2018)"
    ],
  ]

Here 2018 is the year where the book was published. It is not in the
original string, but perhaps you know the information.

Here are the directory names: {json.dumps(directory_names, indent=2)}

Return only a JSON list of tuples without any extra text or markdown."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are a helpful assistant."},
                  {"role": "user", "content": prompt}])

    response_text = response.choices[0].message.content.strip()
    return json.loads(response_text)

def rename_directories(base_paths, dry_run=False):
    """Processes directories and renames them according to ChatGPT suggestions."""
    all_dirs = []

    for base_path in base_paths:
        if not os.path.isdir(base_path):
            print(f"Skipping: {base_path} (not a directory)")
            continue
        all_dirs.extend(
            [os.path.join(base_path, d)
                for d in os.listdir(base_path)
                if os.path.isdir(os.path.join(base_path, d))])

    if not all_dirs:
        print("❌ No valid directories found.")
        return

    old_names = [os.path.basename(d) for d in all_dirs]
    rename_pairs = get_renamed_directories(old_names)

    for old_name, new_name in rename_pairs:
        old_path = next((d for d in all_dirs if os.path.basename(d) == old_name), None)
        if not old_path:
            print(f"⚠️ Skipping: {old_name} (not found)")
            continue

        new_path = os.path.join(os.path.dirname(old_path), new_name)

        if os.path.exists(new_path):
            print(f"⚠️ Skipping: {old_name} → {new_name} (target already exists)")
            continue

        if dry_run:
            print(f"🔍 Dry Run: {old_name} → {new_name}")
        else:
            os.rename(old_path, new_path)
            print(f"✅ Renamed: {old_name} → {new_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rename EPUB directories into a standardized format using ChatGPT.")
    parser.add_argument("directories", nargs="+", help="One or more directories containing EPUB folders.")
    parser.add_argument("--dry-run", action="store_true", help="Preview renaming without making changes.")

    args = parser.parse_args()

    rename_directories(args.directories, dry_run=args.dry_run)

