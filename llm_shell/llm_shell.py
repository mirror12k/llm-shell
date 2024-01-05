import sys
import os
import subprocess
import readline
import glob
import traceback
import argparse
from functools import partial

import llm_shell.chatgpt_support as chatgpt_support
import llm_shell.bedrock_support as bedrock_support
from llm_shell.util import get_prompt, shorten_output, summarize_file, \
    apply_syntax_highlighting, start_spinner, slow_print

version = '0.2.5'
is_command_running = False
history = []
llm_config = {
    'llm_backend': os.getenv('LLM_BACKEND', 'gpt-4-turbo'),
    'llm_instruction': "You are a programming assistant. Help the user build programs and resolve errors.",
    'llm_reindent_with_tabs': True,
    'context_file': [],
    'summary_file': [],
}

support_llm_backends = {
    'gpt-4-turbo': chatgpt_support.send_to_gpt4turbo,
    'gpt-4': chatgpt_support.send_to_gpt4,
    'gpt-3.5-turbo': chatgpt_support.send_to_gpt35turbo,
    'claude-instant-v1': bedrock_support.send_to_claude_instant1,
    'claude-v2.1': bedrock_support.send_to_claude21,
    'hello-world': lambda msg: [ print('llm context:', msg), 'hello world!' ][1],
}

def execute_shell_command(cmd):
    global is_command_running
    is_command_running = True
    output = []
    env = os.environ.copy()
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, env=env)
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                print(line, end='')
                output.append(line)
        process.wait()
    except KeyboardInterrupt:
        process.kill()
        print("^C")
    finally:
        is_command_running = False
    return ''.join(output)

def send_to_llm(context):
    if llm_config['llm_backend'] not in support_llm_backends:
        raise Exception(f"LLM backend '{llm_config['llm_backend']}' is not supported yet.")
    with start_spinner():
        return support_llm_backends[llm_config['llm_backend']](context)

def handle_command(command):
    global history

    def set_file_arg(file_var, *args):
        if len(args) == 0:
            print(f"{file_var} file(s) currently: {llm_config[file_var]}")
        else:
            files = [] if args == ['none'] else [file for arg in args for file in glob.glob(arg) if file]
            llm_config[file_var] = files
            print(f"{file_var} file(s) set to {files}")

    def set_config_arg(module, option, *value, is_boolean=False, censor_value=False):
        if type(module) is dict:
            if len(value) > 0:
                module[option] = ' '.join(value).strip() if not is_boolean else ' '.join(value).strip().lower() == 'true'
                print('set ' + option + ' to', module[option] if not censor_value else '[...]')
            else:
                print(option + ':', module[option] if not censor_value else '[...]')
        else:
            if len(value) > 0:
                setattr(module, option, ' '.join(value).strip() if not is_boolean else ' '.join(value).strip().lower() == 'true')
                print('set ' + option + ' to', getattr(module, option) if not censor_value else '[...]')
            else:
                print(option + ':', getattr(module, option) if not censor_value else '[...]')

    commands = {
        'help': lambda: print("LLM Shell v"+version+""":
    help - Show this help message.
    exit - Exit the shell.
    llm-backend [backend] - Set the language model backend (e.g., gpt-4-turbo, gpt-4, gpt-3.5-turbo).
    llm-instruction [instruction] - Set the instruction for the language model (use 'none' to clear).
    llm-reindent-with-tabs [true/false] - Set the llm_reindent_with_tabs mode (defaults to 'true').
    llm-chatgpt-apikey [apikey] - Set API key for OpenAI's models.
    context [filename] - Set a file to use as context for the language model (use 'none' to clear).
    summary [filename] - Set a summary file to use as context for the language model (use 'none' to clear).
    # [command] - Use the hash sign to prefix any shell command for the language model to process.
    cd [directory] - Change the current working directory.
    [shell command] - Execute any standard shell command.
    Use the tab key to autocomplete commands and file names."""),
        'exit': sys.exit,
        'cd': lambda path: os.chdir(path.strip()),
        'llm-backend': partial(set_config_arg, llm_config, 'llm_backend'),
        'llm-instruction': partial(set_config_arg, llm_config, 'llm_instruction'),
        'llm-reindent-with-tabs': partial(set_config_arg, llm_config, 'llm_reindent_with_tabs', is_boolean=True),
        'llm-chatgpt-apikey': partial(set_config_arg, chatgpt_support, 'chatgpt_api_key', censor_value=True),
        'context': partial(set_file_arg, 'context_file'),
        'summary': partial(set_file_arg, 'summary_file'),
    }

    def process_standard_command():
        output = execute_shell_command(command)
        shortened_output = shorten_output(output)
        history.append({"role": "user", "content": f'$ {command}\n{shortened_output}'})

    cmd_key, *args = command.split(maxsplit=1)
    cmd_key = cmd_key.lower()
    if cmd_key in commands:
        arguments = args[0].split() if args else []
        commands[cmd_key](*arguments)
    elif command.startswith('#'):
        command = command[1:] # Remove the '#'

        # Prepare the context
        context = []

        # Add the last 5 entries from the history
        context.extend(history[-5:])

        # Add the contents of the summary files if they're set
        for file_path in llm_config['summary_file']:
            try:
                with open(file_path, 'r') as file:
                    file_contents = file.read()
                    # Process lines to remove those starting with whitespace
                    file_contents = summarize_file(file_contents)
                    context.append({"role": "user", "content": f'$ cat {file_path} | summarize\n{file_contents}'})
            except FileNotFoundError:
                print(f"Error: File '{file_path}' not found")


        # Add the contents of the context files if they're set
        for file_path in llm_config['context_file']:
            try:
                with open(file_path, 'r') as file:
                    file_contents = file.read()
                    context.append({"role": "user", "content": f'$ cat {file_path}\n{file_contents}'})
            except FileNotFoundError:
                print(f"Error: File '{file_path}' not found")

        context.append({"role": "system", "content": llm_config['llm_instruction']})
        # Append the current command
        context.append({"role": "user", "content": command})

        # Send to LLM and process response
        response = send_to_llm(context)
        highlighted_response = apply_syntax_highlighting(response, reindent_with_tabs=llm_config['llm_reindent_with_tabs'])
        slow_print(highlighted_response)
        # print(highlighted_response)

        history.append({"role": "user", "content": command})
        history.append({"role": "assistant", "content": response})
    else:
        process_standard_command()
    history = history[-5:]

def autocomplete_string(text, state):
    full_input = readline.get_line_buffer()
    split_input = full_input.split()

    # Custom commands for autocompletion
    custom_commands = ['llm-backend ', 'llm-instruction ', 'llm-reindent-with-tabs ', 'llm-chatgpt-apikey ', 'context ', 'summary ']

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
            command = input(get_prompt(llm_config['llm_backend']))
            if command:
                if readline.get_current_history_length() == 0 or command != readline.get_history_item(readline.get_current_history_length()):
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



