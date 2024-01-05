import sys
import os
import subprocess
import getpass
import readline
import glob
import traceback
import argparse

import llm_shell.chatgpt_support
import llm_shell.bedrock_support
from llm_shell.util import get_prompt, shorten_output, summarize_file, apply_syntax_highlighting, start_spinner, slow_print

# Global flag to indicate if a command is currently running
is_command_running = False
llm_backend = os.getenv('LLM_BACKEND', 'gpt-4-turbo')
llm_instruction = "You are a programming assistant. Help the user build programs and resolve errors."
llm_reindent_with_tabs = True
context_file = None
summary_file = None
history = []
version = '0.2.4'

def execute_shell_command(cmd):
    global is_command_running
    is_command_running = True
    output = []

    try:
        env = os.environ.copy()
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)

        # Read output line by line
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(line, end='')  # Print output in real-time
                output.append(line)
        
        # Wait for the command to complete
        process.wait()
    except KeyboardInterrupt:
        process.kill()
        print("^C")
    finally:
        is_command_running = False

    return ''.join(output)

support_llm_backends = {
    'gpt-4-turbo': llm_shell.chatgpt_support.send_to_gpt4turbo,
    'gpt-4': llm_shell.chatgpt_support.send_to_gpt4,
    'gpt-3.5-turbo': llm_shell.chatgpt_support.send_to_gpt35turbo,
    'claude-instant-v1': llm_shell.bedrock_support.send_to_claude_instant1,
    'claude-v2.1': llm_shell.bedrock_support.send_to_claude21,
}

def send_to_llm(context):
    if llm_backend in support_llm_backends:
        stop_spinner_callback = start_spinner()

        try:
            return support_llm_backends[llm_backend](context)
        finally:
            stop_spinner_callback()
    else:
        raise Exception(f"LLM backend '{llm_backend}' is not supported yet.")

def handle_command(command):
    global history, llm_backend, llm_instruction, llm_reindent_with_tabs, context_file, summary_file

    if command.lower() == 'help':
        print("LLM Shell v"+version+":")
        print("  help - Show this help message.")
        print("  exit - Exit the shell.")
        print("  llm-backend [backend] - Set the language model backend (e.g., gpt-4-turbo, gpt-4, gpt-3.5-turbo).")
        print("  llm-instruction [instruction] - Set the instruction for the language model (use 'none' to clear).")
        print("  llm-reindent-with-tabs [true/false] - Set the llm_reindent_with_tabs mode (defaults to 'true').")
        print("  context [filename] - Set a file to use as context for the language model (use 'none' to clear).")
        print("  summary [filename] - Set a summary file to use as context for the language model (use 'none' to clear).")
        print("  # [command] - Use the hash sign to prefix any shell command for the language model to process.")
        print("  cd [directory] - Change the current working directory.")
        print("  [shell command] - Execute any standard shell command.")
        print("  Use the tab key to autocomplete commands and file names.")
    elif command.lower() == 'exit':
        sys.exit()
    elif command.startswith('cd '):
        path = command[3:].strip()
        os.chdir(path)
    elif command.startswith('llm-backend '):
        llm_backend = command[len('llm-backend '):].strip()
        print(f"LLM backend set to {llm_backend}")
    elif command == 'llm-instruction' or command == 'llm-instruction ':
        # Get the current LLM instruction
        print(f"Current LLM instruction: {llm_instruction}")
    elif command.startswith('llm-instruction '):
        # Set the LLM instruction
        instruction = command[len('llm-instruction '):].strip()
        if instruction:
            llm_instruction = instruction
            print(f"LLM instruction set to: {llm_instruction}")
        else:
            print("Please provide an instruction after 'llm-instruction'.")
    elif command == 'llm-reindent-with-tabs' or command == 'llm-reindent-with-tabs ':
        # Get the current LLM instruction
        print(f"Current llm_reindent_with_tabs: {llm_reindent_with_tabs}")
    elif command.startswith('llm-reindent-with-tabs '):
        # Set the LLM instruction
        instruction = command[len('llm-reindent-with-tabs '):].strip().lower()
        if instruction:
            llm_reindent_with_tabs = instruction == 'true'
            print(f"llm_reindent_with_tabs set to: {llm_reindent_with_tabs}")
        else:
            print("Please provide an instruction after 'llm-reindent-with-tabs'.")
    elif command == 'context' or command == 'context ':
        print(f"Current context file(s): {context_file}")
    elif command.startswith('context '):
        context_args = command[len('context '):].strip().split()
        context_files = []
        if len(context_args) == 1 and context_args[0].lower() == 'none':
            context_file = None
        else:
            for arg in context_args:
                expanded_files = glob.glob(arg)
                if expanded_files:
                    context_files.extend(expanded_files)
                else:
                    print(f"Warning: No files matched pattern '{arg}'")
            context_file = context_files if context_files else None
        print(f"Context file(s) set to {context_file}")
    elif command.startswith('summary '):
        summary_args = command[len('summary '):].strip().split()
        summary_files = []
        if len(summary_args) == 1 and summary_args[0].lower() == 'none':
            summary_file = None
        else:
            for arg in summary_args:
                expanded_files = glob.glob(arg)
                if expanded_files:
                    summary_files.extend(expanded_files)
                else:
                    print(f"Warning: No files matched pattern '{arg}'")
            summary_file = summary_files if summary_files else None
        print(f"Summary file(s) set to {summary_file}")
    elif command.startswith('#'):
        command = command[1:]  # Remove the '#'

        # Prepare the context
        context = []

        # Add the last 5 entries from the history
        context.extend(history[-5:])

        # Add the contents of the summary files if they're set
        if summary_file is not None:
            for file_path in summary_file:
                try:
                    with open(file_path, 'r') as file:
                        file_contents = file.read()
                        # Process lines to remove those starting with whitespace
                        file_contents = summarize_file(file_contents)
                        context.append({"role": "user", "content": f'$ cat {file_path} | summarize\n{file_contents}'})
                except FileNotFoundError:
                    print(f"Error: File '{file_path}' not found")


        # Add the contents of the context files if they're set
        if context_file is not None:
            for file_path in context_file:
                try:
                    with open(file_path, 'r') as file:
                        file_contents = file.read()
                        context.append({"role": "user", "content": f'$ cat {file_path}\n{file_contents}'})
                except FileNotFoundError:
                    print(f"Error: File '{file_path}' not found")

        context.append({"role": "system", "content": llm_instruction})
        # Append the current command
        context.append({"role": "user", "content": command})

        # Send to LLM and process response
        response = send_to_llm(context)
        highlighted_response = apply_syntax_highlighting(response, reindent_with_tabs=llm_reindent_with_tabs)
        slow_print(highlighted_response)
        # print(highlighted_response)

        history.append({"role": "user", "content": command})
        history.append({"role": "assistant", "content": response})
    else:
        output = execute_shell_command(command)
        shortened_output = shorten_output(output)  # Implement this function as needed
        history.append({"role": "user", "content": f'$ {command}\n{shortened_output}'})

    # Keep only the last 5 entries in the history
    history = history[-5:]

def autocomplete_string(text, state):
    full_input = readline.get_line_buffer()
    split_input = full_input.split()

    # Custom commands for autocompletion
    custom_commands = ['llm-backend ', 'context ', 'summary ', 'llm-instruction ', 'llm-reindent-with-tabs ']

    if full_input.startswith('llm-backend'):
        # Provide suggestions from the keys of support_llm_backends
        llm_backends = list(support_llm_backends.keys())
        if text:
            completions = [backend for backend in llm_backends if backend.startswith(text)]
        else:
            completions = llm_backends
    elif not text:
        # If no text has been typed, show all custom commands and file completions
        completions = custom_commands + glob.glob('*')
    elif full_input.startswith(('./', '/')) or (len(split_input) > 1 and not full_input.endswith(' ')):
        # Autocomplete file and directory names
        completions = []
        for item in glob.glob(text + '*'):
            if os.path.isdir(item):
                completions.append(item + '/')
            else:
                completions.append(item)
    elif text.startswith('llm') or text.startswith('co') or text.startswith('sum'):
        # If the current text matches the start of our custom commands, suggest them
        completions = [c for c in custom_commands if c.startswith(text)]
    else:
        # Autocomplete program names from PATH
        path_completions = []
        for path_dir in os.environ['PATH'].split(os.pathsep):
            path_completions.extend(glob.glob(os.path.join(path_dir, text) + '*'))
        completions = [os.path.basename(p) for p in path_completions]  # Use basename for commands

    completions = sorted(list(set(completions)))  # Remove duplicates and sort
    return completions[state]

def run_llm_shell():
    # Set the tab completion function
    readline.set_completer_delims(' \t\n;')
    readline.set_completer(autocomplete_string)
    readline.parse_and_bind('tab: complete')

    while True:
        try:
            command = input(get_prompt(llm_backend))

            # Add command to history if it's not a repetition of the last command
            if command.strip() != '':
                history_length = readline.get_current_history_length()
                last_command = readline.get_history_item(history_length) if history_length > 0 else ''

                if command != last_command:
                    readline.add_history(command)

            handle_command(command)

        except EOFError:
            print()  # Print newline
            break  # CTRL+D pressed
        except KeyboardInterrupt:
            # Handle CTRL+C outside of command execution
            print("^C")
            continue
        except Exception as e:
            print("Exception caught: ", e)
            traceback.print_exc()  # This prints the stack trace


def main():
    # Initialize the argument parser
    parser = argparse.ArgumentParser(description='LLM Shell - A shell interface for interacting with language models.')
    # Add the version argument
    parser.add_argument('-v', '--version', action='version', version='LLM Shell v' + version)

    # Parse the arguments
    args = parser.parse_args()

    # Start the LLM shell
    run_llm_shell()



