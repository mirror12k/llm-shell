#!/usr/bin/env python3
import sys
import os
import subprocess
import getpass
import readline
import glob
import traceback

import llm_shell.chatgpt_support
from llm_shell.util import bold_gold, bold_red_and_black_background, get_prompt, shorten_output, change_directory, apply_syntax_highlighting

# Global flag to indicate if a command is currently running
is_command_running = False
llm_backend = os.getenv('LLM_BACKEND', 'gpt-4-turbo')
context_file = None
history = []

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
}

def send_to_llm(context):
    if llm_backend in support_llm_backends:
        return support_llm_backends[llm_backend](context)
    else:
        raise Exception(f"LLM backend '{llm_backend}' is not supported yet.")

def handle_command(command):
    global history, llm_backend, context_file

    if command.lower() == 'help':
        print("Available commands:")
        print("  set-llm [backend] - Set the language model backend (e.g., gpt-4-turbo, gpt-4, gpt-3.5-turbo).")
        print("  context [filename] - Set a file to use as context for the language model (use 'none' to clear).")
        print("  # [command] - Use the hash sign to prefix any command you want the language model to process.")
        print("  exit - Exit the shell.")
    elif command.lower() == 'exit':
        sys.exit()
    elif command.startswith('cd '):
        path = command[3:].strip()
        os.chdir(path)
    elif command.startswith('set-llm '):
        llm_backend = command[len('set-llm '):].strip()
        print(f"LLM backend set to {llm_backend}")
    elif command == 'context' or command == 'context ':
        print(f"Current context file is {context_file}")
    elif command.startswith('context '):
        context_file = command[len('context '):].strip()
        if context_file.lower() == 'none':
            context_file = None
        print(f"Context file set to {context_file}")
    elif command.startswith('#'):
        command = command[1:] # Remove the '#'

        # Prepare the context
        context = []

        # Add the contents of the context file if it's set
        if context_file is not None:
            with open(context_file, 'r') as file:
                file_contents = file.read()
                context.append({"role": "user", "content": f'cat {context_file}\n{file_contents}'})

        # Add the last 5 entries from the history
        context.extend(history[-5:])

        # Append the current command
        context.append({"role": "user", "content": command})

        # Send to LLM and process response
        response = send_to_llm(context)
        highlighted_response = apply_syntax_highlighting(response)
        print(highlighted_response)
        history.append({"role": "assistant", "content": response})
    else:
        output = execute_shell_command(command)
        shortened_output = shorten_output(output)  # Implement this function as needed
        history.append({"role": "user", "content": f'user$ {command}\n{shortened_output}'})

    # Keep only the last 5 entries in the history
    history = history[-5:]

def complete(text, state):
    full_input = readline.get_line_buffer()
    split_input = full_input.split()

    # Custom commands for autocompletion
    custom_commands = ['set-llm ', 'context ']

    if not text:
        # If no text has been typed, show all custom commands and file completions
        completions = custom_commands + glob.glob('*')
    elif full_input.startswith(('./', '/')) or (len(split_input) > 1 and not full_input.endswith(' ')):
        # Autocomplete file and directory names
        completions = glob.glob(text + '*')
    elif text.startswith('se') or text.startswith('co'):
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
    readline.set_completer(complete)
    readline.parse_and_bind('tab: complete')

    while True:
        try:
            sys.stdin.flush()
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
    run_llm_shell()


