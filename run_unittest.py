#!/usr/bin/env python3
import sys
import os
import os.path
import unittest
import tempfile
from unittest.mock import patch, Mock
from io import StringIO
from llm_shell.llm_shell import autocomplete_string, handle_command, ask_llm, llm_config
from llm_shell.util import parse_diff_string, apply_changes

# Define a helper context manager to capture stdout
class CaptureStdout(list):
	def __enter__(self):
		self._stdout = StringIO()
		self._original_stdout = sys.stdout
		sys.stdout = self._stdout
		return self

	def __exit__(self, *args):
		self.extend(self._stdout.getvalue().splitlines())
		del self._stdout  # free up some memory
		sys.stdout = self._original_stdout

class TestLLMShell(unittest.TestCase):

	def test_ls_la_command(self):
		with CaptureStdout() as output:
			handle_command('ls -la')
		# Check if output contains expected text
		self.assertTrue(any(line.startswith('total') for line in output), 'Expected ls -la output not found.')

	def test_cd_command(self):
		# Get the current working directory before the change
		original_cwd = os.getcwd()

		# Create a temporary directory for testing
		with tempfile.TemporaryDirectory() as temp_dir:
			# Change to the temporary directory using the cd command
			handle_command(f'cd {temp_dir}')
			# Get the current working directory after the change
			new_cwd = os.getcwd()

			# Check if the current working directory has been changed to the temp_dir
			self.assertEqual(new_cwd, temp_dir, 'The cd command did not change the working directory correctly.')

		# Clean up by changing back to the original directory
		os.chdir(original_cwd)

	def test_hello_world_backend_command(self):
		# Set llm_config to use the 'hello-world' backend
		llm_config['llm_backend'] = 'hello-world'
		with CaptureStdout() as output:
			# Execute a command that triggers the 'hello-world' backend
			handle_command('# hello')
		# Check if the output contains the expected 'hello world!' response
		self.assertIn('hello world!', output, 'Expected "hello world!" response not found.')

	def test_modify_and_read_llm_config(self):
		# Define a list of test cases with options, values, and expected outputs
		config_options = [
			('llm-backend', 'gpt-3.5-turbo', 'gpt-3.5-turbo', 'set llm_backend to gpt-3.5-turbo'),
			('llm-instruction', 'You are an assistant.', 'You are an assistant.', 'set llm_instruction to You are an assistant.'),
			('llm-history-length', '10', '10', 'set llm_history_length to 10'),
			('llm-reindent-with-tabs', 'false', 'False', 'set llm_reindent_with_tabs to False'),
			('llm-reindent-with-tabs', 'none', 'False', 'set llm_reindent_with_tabs to False'),
			('llm-reindent-with-tabs', 'true', 'True', 'set llm_reindent_with_tabs to True'),
			('llm-reindent-with-tabs', 'TRUE', 'True', 'set llm_reindent_with_tabs to True'),
			('llm-reindent-with-tabs', 'True', 'True', 'set llm_reindent_with_tabs to True'),
			('llm-chatgpt-apikey', 'anything', '[...]', 'set chatgpt_api_key to [...]'),
		]

		for option, value, expected_value, expected_set_output in config_options:
			with self.subTest(option=option, value=value):
				with CaptureStdout() as output:
					handle_command(f'{option} {value}')
				self.assertIn(expected_set_output, output[0], f"Setting {option} failed.")

				with CaptureStdout() as output:
					handle_command(option)
				self.assertIn(expected_value, output[0], f"Getting {option} failed.")

	def test_multiple_py_files_in_context(self):
		# Set llm_config to use the 'hello-world' backend
		llm_config['llm_backend'] = 'hello-world'
		
		# Mock glob to return a list of .py files
		with patch('llm_shell.llm_shell.glob.glob', return_value=['llm_shell/file1.py', 'llm_shell/file2.py']):
			# Mock read_file_contents to return predefined content for files
			with patch('llm_shell.llm_shell.read_file_contents', side_effect=['content of file1', 'content of file2']):
				# Set multiple .py files in context
				handle_command('context llm_shell/*.py')
				handle_command('summary none')
				# Verify if the context files are correctly set
				self.assertEqual(llm_config['context_file'], ['llm_shell/file1.py', 'llm_shell/file2.py'])
				self.assertEqual(llm_config['summary_file'], [])
				# set backend to hello-world
				handle_command('llm-backend hello-world')
				self.assertEqual(llm_config['llm_backend'], 'hello-world')
				
				# Execute a command that triggers the 'hello-world' backend with the expectation it will include context
				with CaptureStdout() as output:
					handle_command('# test command')

				# Check if the output contains the expected file contents
				self.assertIn('content of file1', output[1])
				self.assertIn('content of file2', output[1])

	def test_multiple_py_files_in_summary(self):
		# Set llm_config to use the 'hello-world' backend
		llm_config['llm_backend'] = 'hello-world'
		
		# Mock glob to return a list of .py files
		with patch('llm_shell.llm_shell.glob.glob', return_value=['llm_shell/file1.py', 'llm_shell/file2.py']):
			# Mock read_file_contents to return predefined content for files, with tabs
			# Repeat the contents for both summary and context
			with patch('llm_shell.llm_shell.read_file_contents', side_effect=["\tcontent of file1", "\tcontent of file2"]):
				# Set multiple .py files in summary
				handle_command('summary llm_shell/*.py')
				handle_command('context none')
				# Verify if the summary files are correctly set
				self.assertEqual(llm_config['context_file'], [])
				self.assertEqual(llm_config['summary_file'], ['llm_shell/file1.py', 'llm_shell/file2.py'])
				
				# set backend to hello-world
				handle_command('llm-backend hello-world')
				self.assertEqual(llm_config['llm_backend'], 'hello-world')
				
				# Execute a command that triggers the 'hello-world' backend with the expectation it will include context
				with CaptureStdout() as output:
					handle_command('# test command')

				# Check if the output contains the expected file contents
				# The contents starting with tabs should be omitted
				self.assertNotIn("\tcontent of file1", output[1])
				self.assertNotIn("\tcontent of file2", output[1])

				# As an additional check, confirm that the command to summarize was issued
				self.assertIn('$ cat llm_shell/file1.py | summarize', output[1])
				self.assertIn('$ cat llm_shell/file2.py | summarize', output[1])

	def test_autocomplete(self):
		auto_corrections = [
			('./llm', './llm_shell/'),
			('./llm_shell/ll', './llm_shell/llm_shell.py'),
			('llm-ins', 'llm-instruction '),
			('con', 'context '),
		]
		for text, correction in auto_corrections:
			# Mock readline.get_line_buffer to return the partial text
			with patch('readline.get_line_buffer', return_value=text):
				# Call the autocomplete function
				completion = autocomplete_string(text, 0)
				# Check if the completion is correct
				self.assertEqual(completion, correction)

	def test_regression_context_reading(self):
		
		# Mock glob to return a list of .py files
		with patch('llm_shell.llm_shell.glob.glob', return_value=['llm_shell/file1.py', 'llm_shell/file2.py']):
			# Set multiple .py files in context
			with CaptureStdout() as output:
				handle_command('context llm_shell/*.py')
				handle_command('context')
			# Verify if the context files are still correctly set
			self.assertEqual(llm_config['context_file'], ['llm_shell/file1.py', 'llm_shell/file2.py'])


class TestLLMAgent(unittest.TestCase):

	def test_write_new_file(self):
		if os.path.isfile('/tmp/flask.py'):
			os.remove('/tmp/flask.py')

		diff_response = '''
My diff:
/tmp/flask.py
```
<<<<<<< SEARCH
=======
from flask import Flask
app = Flask(__name__)
@app.route('/')
def hello_world():
	return 'Hello, World!'
if __name__ == '__main__':
	app.run(debug=True)
>>>>>>> REPLACE

```
That was my diff.
'''
		for filepath, search_block, replace_block in parse_diff_string(diff_response):
			print(f"Applying changes to {filepath}...")
			self.assertTrue(apply_changes(filepath, search_block, replace_block), 'Expected apply changes to succeed')
		self.assertTrue(os.path.isfile('/tmp/flask.py'), 'Expected /tmp/flask.py to be a file')
		with open('/tmp/flask.py', 'r') as f:
			contents = f.read()
		self.assertEqual(contents, '''from flask import Flask
app = Flask(__name__)
@app.route('/')
def hello_world():
	return 'Hello, World!'
if __name__ == '__main__':
	app.run(debug=True)''', 'Expected flask.py contents match diff')
		os.remove('/tmp/flask.py')

	def test_write_more_file(self):
		if os.path.isfile('/tmp/flask.py'):
			os.remove('/tmp/flask.py')

		diff_response = '''
My diff:
`/tmp/flask.py`
```
<<<<<<< SEARCH
=======
from flask import Flask
>>>>>>> REPLACE
```

```
<<<<<<< SEARCH
from flask import Flask
=======
import sys
from flask import Flask
>>>>>>> REPLACE
```

That was my diff.
'''
		for filepath, search_block, replace_block in parse_diff_string(diff_response):
			print(f"Applying changes to {filepath}...")
			self.assertTrue(apply_changes(filepath, search_block, replace_block), 'Expected apply changes to succeed')
		self.assertTrue(os.path.isfile('/tmp/flask.py'), 'Expected /tmp/flask.py to be a file')
		with open('/tmp/flask.py', 'r') as f:
			contents = f.read()
		self.assertEqual(contents, '''import sys
from flask import Flask''', 'Expected flask.py contents match diff')
		os.remove('/tmp/flask.py')

	def test_write_multi_file(self):
		if os.path.isfile('/tmp/flask.py'):
			os.remove('/tmp/flask.py')
		if os.path.isfile('/tmp/runtest.py'):
			os.remove('/tmp/runtest.py')

		diff_response = '''
My diff:
```
/tmp/flask.py
<<<<<<< SEARCH
=======
from flask import Flask
>>>>>>> REPLACE
```

```
`/tmp/runtest.py`
<<<<<<< SEARCH
=======
import unittest
>>>>>>> REPLACE
```

```
<<<<<<< SEARCH
import unittest
=======
import unittest
import sys
>>>>>>> REPLACE
```

That was my diff.
'''
		for filepath, search_block, replace_block in parse_diff_string(diff_response):
			print(f"Applying changes to {filepath}...")
			self.assertTrue(apply_changes(filepath, search_block, replace_block), 'Expected apply changes to succeed')
		self.assertTrue(os.path.isfile('/tmp/flask.py'), 'Expected /tmp/flask.py to be a file')
		self.assertTrue(os.path.isfile('/tmp/runtest.py'), 'Expected /tmp/runtest.py to be a file')
		with open('/tmp/flask.py', 'r') as f:
			contents = f.read()
		self.assertEqual(contents, '''from flask import Flask''', 'Expected flask.py contents match diff')
		with open('/tmp/runtest.py', 'r') as f:
			contents = f.read()
		self.assertEqual(contents, '''import unittest
import sys''', 'Expected runtest.py contents match diff')
		os.remove('/tmp/flask.py')
		os.remove('/tmp/runtest.py')

	def test_edit_file(self):
		if os.path.isfile('/tmp/flask.py'):
			os.remove('/tmp/flask.py')

		with open('/tmp/flask.py', 'w') as f:
			f.write('from flask import Flask')

		diff_response = '''
My diff:
/tmp/flask.py
```
<<<<<<< SEARCH
from flask import Flask
=======
from flask import Flask
import sys
>>>>>>> REPLACE
```
That was my diff.
'''

		for filepath, search_block, replace_block in parse_diff_string(diff_response):
			print(f"Applying changes to {filepath}...")
			self.assertTrue(apply_changes(filepath, search_block, replace_block), 'Expected apply changes to succeed')
		self.assertTrue(os.path.isfile('/tmp/flask.py'), 'Expected /tmp/flask.py to be a file')
		with open('/tmp/flask.py', 'r') as f:
			contents = f.read()
		self.assertEqual(contents, '''from flask import Flask
import sys''', 'Expected flask.py contents match diff')

		os.remove('/tmp/flask.py')

	def test_edit_file_with_spacing(self):
		if os.path.isfile('/tmp/flask.py'):
			os.remove('/tmp/flask.py')

		with open('/tmp/flask.py', 'w') as f:
			f.write('from flask import Flask\n\n\nprint("hello")')

		diff_response = '''
My diff:
/tmp/flask.py
```
<<<<<<< SEARCH
from flask import Flask
print("hello")
=======
import sys
print(sys.argv)
print("hello")
>>>>>>> REPLACE
```
That was my diff.
'''

		for filepath, search_block, replace_block in parse_diff_string(diff_response):
			print(f"Applying changes to {filepath}...")
			self.assertTrue(apply_changes(filepath, search_block, replace_block), 'Expected apply changes to succeed')
		self.assertTrue(os.path.isfile('/tmp/flask.py'), 'Expected /tmp/flask.py to be a file')
		with open('/tmp/flask.py', 'r') as f:
			contents = f.read()
		self.assertEqual(contents, '''import sys
print(sys.argv)
print("hello")''', 'Expected flask.py contents match diff')

		os.remove('/tmp/flask.py')

	def test_edit_file_with_mess(self):
		if os.path.isfile('/tmp/flask.py'):
			os.remove('/tmp/flask.py')

		with open('/tmp/flask.py', 'w') as f:
			f.write('from flask import Flask\nimport asdf\n\n\nprint("hello")\nprint("wat?")')

		diff_response = '''
My diff:
/tmp/flask.py
```
<<<<<<< SEARCH
import asdf
print("hello")
=======
import sys

print("goodbye")
>>>>>>> REPLACE
```
That was my diff.
'''

		for filepath, search_block, replace_block in parse_diff_string(diff_response):
			print(f"Applying changes to {filepath}...")
			self.assertTrue(apply_changes(filepath, search_block, replace_block), 'Expected apply changes to succeed')
		self.assertTrue(os.path.isfile('/tmp/flask.py'), 'Expected /tmp/flask.py to be a file')
		with open('/tmp/flask.py', 'r') as f:
			contents = f.read()
		self.assertEqual(contents, 'from flask import Flask\nimport sys\n\nprint("goodbye")\nprint("wat?")', 'Expected flask.py contents match diff')

		os.remove('/tmp/flask.py')

	def test_edit_file_with_underindented_code(self):
		if os.path.isfile('/tmp/flask.py'):
			os.remove('/tmp/flask.py')

		with open('/tmp/flask.py', 'w') as f:
			f.write('from flask import Flask\ndef myfun():\n\tprint("hello")\n\n\tprint("wat?")')

		diff_response = '''/tmp/flask.py
```
<<<<<<< SEARCH
print("hello")
print("wat?")
=======
if True:
    print("hello")
>>>>>>> REPLACE
```'''

		for filepath, search_block, replace_block in parse_diff_string(diff_response):
			print(f"Applying changes to {filepath}...")
			self.assertTrue(apply_changes(filepath, search_block, replace_block), 'Expected apply changes to succeed')
		self.assertTrue(os.path.isfile('/tmp/flask.py'), 'Expected /tmp/flask.py to be a file')
		with open('/tmp/flask.py', 'r') as f:
			contents = f.read()
		self.assertEqual(contents, 'from flask import Flask\ndef myfun():\n    if True:\n        print("hello")', 'Expected flask.py contents match diff')

		os.remove('/tmp/flask.py')

class TestAskLLM(unittest.TestCase):
    def setUp(self):
        self.original_stdout = sys.stdout
        self.captured_stdout = StringIO()
        sys.stdout = self.captured_stdout

    def tearDown(self):
        sys.stdout = self.original_stdout

    @patch('llm_shell.llm_shell.handle_llm_command')
    def test_ask_llm_with_topic(self, mock_handle_llm_command):
        sys.argv = ['ask_llm.py', 'What is the capital of France?']
        ask_llm()
        mock_handle_llm_command.assert_called_with('What is the capital of France?', show_spinner=False)

    @patch('llm_shell.llm_shell.handle_llm_command')
    def test_ask_llm_with_stdin(self, mock_handle_llm_command):
        sys.stdin = StringIO('This is some input from stdin.\n')
        sys.argv = ['ask_llm.py', '--stdin']
        ask_llm()
        mock_handle_llm_command.assert_called_with('This is some input from stdin.\n\n\n\n', show_spinner=False)

    @patch('llm_shell.llm_shell.handle_llm_command')
    def test_ask_llm_with_topic_and_stdin(self, mock_handle_llm_command):
        sys.stdin = StringIO('This is some input from stdin.\n')
        sys.argv = ['ask_llm.py', '--stdin', 'What is the capital of France?']
        ask_llm()
        mock_handle_llm_command.assert_called_with('This is some input from stdin.\n\n\n\nWhat is the capital of France?', show_spinner=False)

    @patch('llm_shell.llm_shell.handle_llm_command')
    @patch('llm_shell.llm_shell.load_llm_config_from_file')
    def test_ask_llm_with_context_file(self, mock_load_llm_config, mock_handle_llm_command):
        mock_load_llm_config.return_value = None
        sys.argv = ['ask_llm.py', '-c', 'file1.py', '-c', 'file2.py', 'What is the capital of France?']
        ask_llm()
        self.assertEqual(llm_config['context_file'], ['file1.py', 'file2.py'])
        mock_handle_llm_command.assert_called_with('What is the capital of France?', show_spinner=False)

    def test_ask_llm_no_input(self):
        sys.argv = ['ask_llm.py']
        ask_llm()
        # self.assertRaises(SystemExit, ask_llm)
        self.assertIn('No input provided', self.captured_stdout.getvalue())

if __name__ == '__main__':
	unittest.main()
