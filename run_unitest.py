#!/usr/bin/env python3
import sys
import os
import unittest
import tempfile
from unittest.mock import patch, Mock
from io import StringIO
from llm_shell.llm_shell import autocomplete_string, handle_command, llm_config

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

	def test_autocomplete_llm_she_to_llm_shell(self):
		# Mock readline.get_line_buffer to return the partial text
		with patch('readline.get_line_buffer', return_value='./llm'):
			# Call the autocomplete function
			completion = autocomplete_string('./llm', 0)
			# Check if the completion is correct
			self.assertEqual(completion, './llm_shell/')
		with patch('readline.get_line_buffer', return_value='./llm_shell/ll'):
			# Call the autocomplete function
			completion = autocomplete_string('./llm_shell/ll', 0)
			# Check if the completion is correct
			self.assertEqual(completion, './llm_shell/llm_shell.py')
		with patch('readline.get_line_buffer', return_value='llm-ins'):
			# Call the autocomplete function
			completion = autocomplete_string('llm-ins', 0)
			# Check if the completion is correct
			self.assertEqual(completion, 'llm-instruction ')


if __name__ == '__main__':
	unittest.main()
