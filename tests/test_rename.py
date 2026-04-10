import os
import shutil
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
import sys
from rename import main

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

    @patch("rename.load_api_key", return_value="fake_api_key")
    @patch("rename.OpenAI")
    def test_rename_with_d_option(self, mock_openai, mock_load_api_key):
        # Mock the OpenAI client and its response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = '[["sub_dir1", "new_dir1"], ["sub_dir2", "new_dir2"]]'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Run the main function with arguments
        with patch.object(sys, 'argv', ['rename.py', '-d', self.test_dir, '--dry-run']):
            main()

        # Check the output
        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: sub_dir1 → new_dir1", output)
        self.assertIn("Dry Run: sub_dir2 → new_dir2", output)

    @patch("rename.load_api_key", return_value="fake_api_key")
    @patch("rename.OpenAI")
    def test_rename_with_direct_args(self, mock_openai, mock_load_api_key):
        # Mock the OpenAI client and its response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = '[["sub_dir1", "new_dir1"], ["sub_dir2", "new_dir2"]]'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Run the main function with arguments
        with patch.object(sys, 'argv', ['rename.py', self.sub_dir1, self.sub_dir2, '--dry-run']):
            main()

        # Check the output
        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: sub_dir1 → new_dir1", output)
        self.assertIn("Dry Run: sub_dir2 → new_dir2", output)

    @patch("rename.load_api_key", return_value="fake_api_key")
    @patch("rename.OpenAI")
    def test_rename_with_both_args(self, mock_openai, mock_load_api_key):
        # Mock the OpenAI client and its response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = '[["sub_dir1", "new_dir1"], ["sub_dir2", "new_dir2"], ["another_dir", "new_another_dir"]]'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        another_dir = os.path.join(self.test_dir, "another_dir")
        os.makedirs(another_dir, exist_ok=True)

        # Run the main function with arguments
        with patch.object(sys, 'argv', ['rename.py', another_dir, '-d', self.test_dir, '--dry-run']):
            main()

        # Check the output
        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: sub_dir1 → new_dir1", output)
        self.assertIn("Dry Run: sub_dir2 → new_dir2", output)
        self.assertIn("Dry Run: another_dir → new_another_dir", output)

    @patch("rename.load_api_key", return_value="fake_api_key")
    @patch("rename.OpenAI")
    def test_invalid_d_option_is_file(self, mock_openai, mock_load_api_key):
        file_path = os.path.join(self.test_dir, "test_file.txt")
        with open(file_path, "w") as f:
            f.write("test")

        with patch.object(sys, 'argv', ['rename.py', '-d', file_path]):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertEqual(cm.exception.code, 1)

        output = self.captured_stdout.getvalue()
        self.assertIn(f"Error: '{file_path}' exists but is not a directory.", output)

    @patch("rename.load_api_key", return_value="fake_api_key")
    @patch("rename.OpenAI")
    def test_no_valid_items(self, mock_openai, mock_load_api_key):
        with patch.object(sys, 'argv', ['rename.py', 'non_existent_dir']):
            with self.assertRaises(SystemExit) as cm:
                main()
        self.assertEqual(cm.exception.code, 1)

        output = self.captured_stdout.getvalue()
        self.assertIn("No valid directories or EPUB files found to rename.", output)

    @patch("rename.load_api_key", return_value="fake_api_key")
    @patch("rename.OpenAI")
    def test_rename_with_epub_files(self, mock_openai, mock_load_api_key):
        # Mock the OpenAI client and its response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = '[["book1.epub", "Author - Title1 (2020)"], ["sub_dir1", "Author - Title2 (2021)"]]'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Create an EPUB file in the test directory
        epub_path = os.path.join(self.test_dir, "book1.epub")
        with open(epub_path, "w") as f:
            f.write("fake epub content")

        # Run the main function with the directory containing both a file and a directory
        with patch.object(sys, 'argv', ['rename.py', '-d', self.test_dir, '--dry-run']):
            main()

        # Check the output
        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: book1.epub → Author - Title1 (2020)/Author - Title1 (2020).epub", output)
        self.assertIn("Dry Run: sub_dir1 → Author - Title2 (2021)", output)

    @patch("rename.load_api_key", return_value="fake_api_key")
    @patch("rename.OpenAI")
    def test_rename_with_trailing_slash(self, mock_openai, mock_load_api_key):
        # Mock the OpenAI client and its response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = '[["sub_dir1", "new_dir1"]]'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Run the main function with a directory argument that has a trailing slash
        dir_with_slash = self.sub_dir1 + os.sep
        with patch.object(sys, 'argv', ['rename.py', dir_with_slash, '--dry-run']):
            main()

        # Check the output
        output = self.captured_stdout.getvalue()
        # If it handles trailing slash correctly, it should find 'sub_dir1' as basename
        self.assertIn("Dry Run: sub_dir1 → new_dir1", output)

    @patch("rename.load_api_key", return_value="fake_api_key")
    @patch("rename.OpenAI")
    def test_rename_with_multiple_trailing_slashes(self, mock_openai, mock_load_api_key):
        # Mock the OpenAI client and its response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = '[["sub_dir1", "new_dir1"]]'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Run the main function with a directory argument that has multiple trailing slashes
        dir_with_slashes = self.sub_dir1 + os.sep + os.sep + os.sep
        with patch.object(sys, 'argv', ['rename.py', dir_with_slashes, '--dry-run']):
            main()

        # Check the output
        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: sub_dir1 → new_dir1", output)

    @patch("rename.load_api_key", return_value="fake_api_key")
    @patch("rename.OpenAI")
    def test_rename_positional_epub_file(self, mock_openai, mock_load_api_key):
        # Mock the OpenAI client and its response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = '[["standalone.epub", "Author - Title (2022)"]]'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Create a standalone EPUB file
        epub_path = os.path.join(self.test_dir, "standalone.epub")
        with open(epub_path, "w") as f:
            f.write("fake epub content")

        # Run the main function with the EPUB file as a positional argument
        with patch.object(sys, 'argv', ['rename.py', epub_path, '--dry-run']):
            main()

        # Check the output
        output = self.captured_stdout.getvalue()
        self.assertIn("Dry Run: standalone.epub → Author - Title (2022)/Author - Title (2022).epub", output)

if __name__ == "__main__":
    unittest.main()
