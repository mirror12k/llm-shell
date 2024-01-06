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

version = '0.2.7'
is_command_running = False
history = []
llm_config = {
    'llm_backend': os.getenv('LLM_BACKEND', 'gpt-4-turbo'),
    'llm_instruction': "You are a programming assistant. Help the user build programs and resolve errors.",
    'llm_reindent_with_tabs': True,
    'llm_history_length': 5,
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
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, env=os.environ)
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

def update_history(role, content):
    global history
    history.append({"role": role, "content": content})
    history = history[-llm_config['llm_history_length']:]

def read_file_contents(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
        return None

def handle_llm_command(command):
    # Prepare the context
    context = history[-llm_config['llm_history_length']:]

    # Add file contents to context with summarization or as is
    for file_var, summarize in (('summary_file', True), ('context_file', False)):
        for file_path in llm_config[file_var]:
            file_contents = read_file_contents(file_path)
            if file_contents:
                if summarize:
                    file_contents = summarize_file(file_contents)
                context.append({"role": "user", "content": f'$ cat {file_path}{" | summarize" if summarize else ""}\n{file_contents}'})

    context.append({"role": "system", "content": llm_config['llm_instruction']})
    context.append({"role": "user", "content": command})

    # Send to LLM and process response
    response = send_to_llm(context)
    highlighted_response = apply_syntax_highlighting(response, reindent_with_tabs=llm_config['llm_reindent_with_tabs'])
    slow_print(highlighted_response)

    update_history("user", command)
    update_history("assistant", response)


def set_file_arg(file_var, *args):
    if len(args) > 0:
        files = [] if len(args) == 1 and args[0].lower() == 'none' else [file for arg in args for file in glob.glob(arg) if file]
        llm_config[file_var] = files
        print(f"{file_var} file(s) set to {files}")
    else:
        print(f"{file_var} file(s): {llm_config[file_var]}")

def set_config_arg(module, option, *value, custom_parser=None, censor_value=False):
    if type(module) is dict:
        if len(value) > 0:
            module[option] = ' '.join(value).strip() if not custom_parser else custom_parser(' '.join(value).strip())
            print('set ' + option + ' to', module[option] if not censor_value else '[...]')
        else:
            print(option + ':', module[option] if not censor_value else '[...]')
    else:
        if len(value) > 0:
            setattr(module, option, ' '.join(value).strip() if not custom_parser else custom_parser(' '.join(value).strip()))
            print('set ' + option + ' to', getattr(module, option) if not censor_value else '[...]')
        else:
            print(option + ':', getattr(module, option) if not censor_value else '[...]')

commands = {
    'help': lambda: print(f"""LLM Shell v{version}:
help - Show this help message.
exit - Exit the shell.
llm-backend [backend] - Set the language model backend (e.g., gpt-4-turbo, gpt-4, gpt-3.5-turbo).
llm-instruction [instruction] - Set the instruction for the language model (use 'none' to clear).
llm-reindent-with-tabs [true/false] - Set the llm_reindent_with_tabs mode (defaults to 'true').
llm-history-length [5] - Set the length of history to send to llms. More history == more cost.
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
    'llm-reindent-with-tabs': partial(set_config_arg, llm_config, 'llm_reindent_with_tabs', custom_parser=lambda s: s.lower() == 'true'),
    'llm-history-length': partial(set_config_arg, llm_config, 'llm_history_length', custom_parser=lambda s: int(s)),
    'llm-chatgpt-apikey': partial(set_config_arg, chatgpt_support, 'chatgpt_api_key', censor_value=True),
    'context': partial(set_file_arg, 'context_file'),
    'summary': partial(set_file_arg, 'summary_file'),
}

def process_standard_command(command):
    output = execute_shell_command(command)
    shortened_output = shorten_output(output)
    update_history('user', f'$ {command}\n{shortened_output}')

def handle_command(command):
    cmd_key, *args = command.split(maxsplit=1)
    cmd_key = cmd_key.lower()
    if cmd_key in commands:
        arguments = args[0].split() if args else []
        commands[cmd_key](*arguments)
    elif command.startswith('#'):
        command = command[1:] # Remove the '#'
        handle_llm_command(command)
    else:
        process_standard_command(command)

def autocomplete_string(text, state):
    full_input = readline.get_line_buffer()
    split_input = full_input.split()

    # Custom commands for autocompletion
    custom_commands = ['llm-backend ', 'llm-instruction ', 'llm-reindent-with-tabs ', 'llm-history-length ', 'llm-chatgpt-apikey ', 'context ', 'summary ']

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



