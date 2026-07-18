import os
import shutil
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
import sys

import anthropic
import httpx
import openai

from rename import main

OPENAI_CONFIG = {
    "provider": "openai",
    "openai": {"model": "gpt-4o-mini", "api_key": "fake_api_key"},
}

ANTHROPIC_CONFIG = {
    "provider": "anthropic",
    "anthropic": {"model": "claude-opus-4-8", "api_key": "fake_api_key"},
}


def mock_openai_client(response_json):
    """Builds a mocked OpenAI client returning the given chat completion text."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = response_json
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def mock_anthropic_client(response_json):
    """Builds a mocked Anthropic client returning the given message text."""
    mock_client = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = response_json
    mock_response = MagicMock()
    mock_response.content = [text_block]
    mock_response.stop_reason = "end_turn"
    mock_client.messages.create.return_value = mock_response
    return mock_client


class TestRenameScript(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_rename_dir"
        os.makedirs(self.test_dir, exist_ok=True)
        self.sub_dir1 = os.path.join(self.test_dir, "sub_dir1")
        self.sub_dir2 = os.path.join(self.test_dir, "sub_dir2")
        os.makedirs(self.sub_dir1, exist_ok=True)
        os.makedirs(self.sub_dir2, exist_ok=True)
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        sys.stdout = self.captured_stdout = StringIO()
        sys.stderr = self.captured_stderr = StringIO()

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

    @patch("rename.load_config", return_value=OPENAI_CONFIG)
    @patch("rename.OpenAI")
    def test_rename_with_d_option(self, mock_openai, mock_load_config):
        mock_openai.return_value = mock_openai_client(
            '[["sub_dir1", "new_dir1"], ["sub_dir2", "new_dir2"]]'
        )

        with patch.object(sys, 'argv', ['rename.py', '-d', self.test_dir, '--dry-run']):
            main()

        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: sub_dir1 → new_dir1", output)
        self.assertIn("Dry Run: sub_dir2 → new_dir2", output)

    @patch("rename.load_config", return_value=OPENAI_CONFIG)
    @patch("rename.OpenAI")
    def test_rename_with_direct_args(self, mock_openai, mock_load_config):
        mock_openai.return_value = mock_openai_client(
            '[["sub_dir1", "new_dir1"], ["sub_dir2", "new_dir2"]]'
        )

        with patch.object(sys, 'argv', ['rename.py', self.sub_dir1, self.sub_dir2, '--dry-run']):
            main()

        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: sub_dir1 → new_dir1", output)
        self.assertIn("Dry Run: sub_dir2 → new_dir2", output)

    @patch("rename.load_config", return_value=OPENAI_CONFIG)
    @patch("rename.OpenAI")
    def test_rename_with_both_args(self, mock_openai, mock_load_config):
        mock_openai.return_value = mock_openai_client(
            '[["sub_dir1", "new_dir1"], ["sub_dir2", "new_dir2"], ["another_dir", "new_another_dir"]]'
        )

        another_dir = os.path.join(self.test_dir, "another_dir")
        os.makedirs(another_dir, exist_ok=True)

        with patch.object(sys, 'argv', ['rename.py', another_dir, '-d', self.test_dir, '--dry-run']):
            main()

        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: sub_dir1 → new_dir1", output)
        self.assertIn("Dry Run: sub_dir2 → new_dir2", output)
        self.assertIn("Dry Run: another_dir → new_another_dir", output)

    @patch("rename.load_config", return_value=OPENAI_CONFIG)
    @patch("rename.OpenAI")
    def test_invalid_d_option_is_file(self, mock_openai, mock_load_config):
        file_path = os.path.join(self.test_dir, "test_file.txt")
        with open(file_path, "w") as f:
            f.write("test")

        with patch.object(sys, 'argv', ['rename.py', '-d', file_path]):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertEqual(cm.exception.code, 1)

        output = self.captured_stdout.getvalue()
        self.assertIn(f"Error: '{file_path}' exists but is not a directory.", output)

    @patch("rename.load_config", return_value=OPENAI_CONFIG)
    @patch("rename.OpenAI")
    def test_no_valid_items(self, mock_openai, mock_load_config):
        with patch.object(sys, 'argv', ['rename.py', 'non_existent_dir']):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertEqual(cm.exception.code, 1)

        output = self.captured_stdout.getvalue()
        self.assertIn("No valid directories or EPUB files found to rename.", output)

    @patch("rename.load_config", return_value=OPENAI_CONFIG)
    @patch("rename.OpenAI")
    def test_rename_with_epub_files(self, mock_openai, mock_load_config):
        mock_openai.return_value = mock_openai_client(
            '[["book1.epub", "Author - Title1 (2020)"], ["sub_dir1", "Author - Title2 (2021)"]]'
        )

        epub_path = os.path.join(self.test_dir, "book1.epub")
        with open(epub_path, "w") as f:
            f.write("fake epub content")

        with patch.object(sys, 'argv', ['rename.py', '-d', self.test_dir, '--dry-run']):
            main()

        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: book1.epub → Author - Title1 (2020)/Author - Title1 (2020).epub", output)
        self.assertIn("Dry Run: sub_dir1 → Author - Title2 (2021)", output)

    @patch("rename.load_config", return_value=OPENAI_CONFIG)
    @patch("rename.OpenAI")
    def test_rename_with_trailing_slash(self, mock_openai, mock_load_config):
        mock_openai.return_value = mock_openai_client('[["sub_dir1", "new_dir1"]]')

        dir_with_slash = self.sub_dir1 + os.sep
        with patch.object(sys, 'argv', ['rename.py', dir_with_slash, '--dry-run']):
            main()

        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: sub_dir1 → new_dir1", output)

    @patch("rename.load_config", return_value=OPENAI_CONFIG)
    @patch("rename.OpenAI")
    def test_rename_with_multiple_trailing_slashes(self, mock_openai, mock_load_config):
        mock_openai.return_value = mock_openai_client('[["sub_dir1", "new_dir1"]]')

        dir_with_slashes = self.sub_dir1 + os.sep + os.sep + os.sep
        with patch.object(sys, 'argv', ['rename.py', dir_with_slashes, '--dry-run']):
            main()

        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: sub_dir1 → new_dir1", output)

    @patch("rename.load_config", return_value=OPENAI_CONFIG)
    @patch("rename.OpenAI")
    def test_rename_positional_epub_file(self, mock_openai, mock_load_config):
        mock_openai.return_value = mock_openai_client(
            '[["standalone.epub", "Author - Title (2022)"]]'
        )

        epub_path = os.path.join(self.test_dir, "standalone.epub")
        with open(epub_path, "w") as f:
            f.write("fake epub content")

        with patch.object(sys, 'argv', ['rename.py', epub_path, '--dry-run']):
            main()

        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: standalone.epub → Author - Title (2022)/Author - Title (2022).epub", output)

    @patch("rename.load_config", return_value=ANTHROPIC_CONFIG)
    @patch("rename.Anthropic")
    def test_rename_with_anthropic_provider(self, mock_anthropic, mock_load_config):
        mock_anthropic.return_value = mock_anthropic_client(
            '[["sub_dir1", "new_dir1"], ["sub_dir2", "new_dir2"]]'
        )

        with patch.object(sys, 'argv', ['rename.py', '-d', self.test_dir, '--dry-run']):
            main()

        mock_anthropic.assert_called_once_with(api_key="fake_api_key")
        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: sub_dir1 → new_dir1", output)
        self.assertIn("Dry Run: sub_dir2 → new_dir2", output)

    @patch("rename.load_config", return_value=ANTHROPIC_CONFIG)
    @patch("rename.Anthropic")
    def test_anthropic_reply_with_markdown_fence(self, mock_anthropic, mock_load_config):
        mock_anthropic.return_value = mock_anthropic_client(
            '```json\n[["sub_dir1", "new_dir1"]]\n```'
        )

        with patch.object(sys, 'argv', ['rename.py', self.sub_dir1, '--dry-run']):
            main()

        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: sub_dir1 → new_dir1", output)

    @patch("rename.load_config", return_value=ANTHROPIC_CONFIG)
    @patch("rename.Anthropic")
    def test_anthropic_api_error_shows_nice_message(self, mock_anthropic, mock_load_config):
        message = "Your credit balance is too low to access the Anthropic API."
        response = httpx.Response(
            400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.BadRequestError(
            message, response=response, body=None
        )
        mock_anthropic.return_value = mock_client

        with patch.object(sys, 'argv', ['rename.py', self.sub_dir1, '--dry-run']):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertEqual(cm.exception.code, 1)

        errors = self.captured_stderr.getvalue()
        self.assertIn("credit balance is too low", errors)
        self.assertNotIn("Traceback", errors)

    @patch("rename.load_config", return_value=OPENAI_CONFIG)
    @patch("rename.OpenAI")
    def test_openai_api_error_shows_nice_message(self, mock_openai, mock_load_config):
        message = "You exceeded your current quota."
        response = httpx.Response(
            429, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = openai.RateLimitError(
            message, response=response, body=None
        )
        mock_openai.return_value = mock_client

        with patch.object(sys, 'argv', ['rename.py', self.sub_dir1, '--dry-run']):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertEqual(cm.exception.code, 1)

        errors = self.captured_stderr.getvalue()
        self.assertIn("exceeded your current quota", errors)
        self.assertNotIn("Traceback", errors)

    @patch("rename.load_config", return_value={"provider": "gemini"})
    def test_unknown_provider(self, mock_load_config):
        with patch.object(sys, 'argv', ['rename.py', self.sub_dir1, '--dry-run']):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertEqual(cm.exception.code, 1)

        output = self.captured_stdout.getvalue()
        self.assertIn("unknown provider 'gemini'", output)


if __name__ == "__main__":
    unittest.main()
