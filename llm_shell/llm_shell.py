import sys
import os
import subprocess
import readline
import glob
import traceback
import argparse
from functools import partial

import llm_shell.experimental_llm_agent as experimental_llm_agent
import llm_shell.chatgpt_support as chatgpt_support
import llm_shell.bedrock_support as bedrock_support
from llm_shell.util import read_file_contents, get_prompt, shorten_output, summarize_file, \
    apply_syntax_highlighting, start_spinner, slow_print, \
    parse_bash_string, parse_diff_string, apply_changes, \
    save_llm_config_to_file, load_llm_config_from_file, record_debug_history

version = '0.5.0'
history = []
llm_config = {
    'llm_backend': os.getenv('LLM_BACKEND', 'openai-gpt-4o'),
    'llm_instruction': "You are a programming assistant. Help the user build programs and resolve errors.",
    'llm_reindent_with_tabs': False,
    'llm_history_length': 5,
    'experimental_llm_agent': False,
    'experimental_verifier_command': None,
    'experimental_bash_agent': None,
    'context_file': [],
    'summary_file': [],
    'record_debug_history': False,  # Add a new config option for recording debug history
}

support_llm_backends = {
    'openai-o1-preview': chatgpt_support.send_to_o1,
    'openai-o1-mini': chatgpt_support.send_to_o1mini,
    'openai-gpt-4o': chatgpt_support.send_to_gpt4o,
    'openai-gpt-4o-mini': chatgpt_support.send_to_gpt4omini,
    'openai-gpt-4-turbo': chatgpt_support.send_to_gpt4turbo,
    'openai-gpt-4': chatgpt_support.send_to_gpt4,
    'openai-gpt-3.5-turbo': chatgpt_support.send_to_gpt35turbo,
    'claude-instant-v1': bedrock_support.send_to_claude_instant1,
    'claude-2.1': bedrock_support.send_to_claude21,
    'claude-3-sonnet': bedrock_support.send_to_claude3sonnet,
    'claude-3.5-sonnet': bedrock_support.send_to_claude35sonnet,
    'claude-3-haiku': bedrock_support.send_to_claude3haiku,
    'claude-3-opus': bedrock_support.send_to_claude3opus,
    'hello-world': lambda msg: [ print('llm context:', msg), '''hello world!''' ][1],
}

def execute_shell_command(cmd):
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
    if process.returncode != 0:
        print('process exited with code: ', process.returncode)
    return ''.join(output), process.returncode

def send_to_llm(context, show_spinner=True):
    if llm_config['llm_backend'] not in support_llm_backends:
        raise Exception(f"LLM backend '{llm_config['llm_backend']}' is not supported yet.")
    backend_fun = support_llm_backends[llm_config['llm_backend']]
    if show_spinner:
        with start_spinner():
            return backend_fun(context)
    else:
        return backend_fun(context)

def update_history(role, content):
    global history
    history.append({"role": role, "content": content})
    history = history[-llm_config['llm_history_length']:]

def execute_verifier_command(verifier_command):
    if verifier_command:
        print(f"Executing verifier command: {verifier_command}")
        process_standard_command(verifier_command)

def handle_llm_command(command, do_slow_print=False, **kwargs):
    # Prepare the context
    context = history[-llm_config['llm_history_length']:]

    # Add file contents to context with summarization or as is
    context_file_entries = []
    for file_var, summarize in (('summary_file', True), ('context_file', False)):
        for file_path in llm_config[file_var]:
            file_contents = read_file_contents(file_path)
            if file_contents:
                if summarize:
                    file_contents = summarize_file(file_contents)
                context_file_entries.append({"role": "user", "content": f'$ cat {file_path}{" | summarize" if summarize else ""}\n{file_contents}'})
    context.extend(context_file_entries)

    context.append({"role": "system", "content": llm_config['llm_instruction']})
    context.append({"role": "user", "content": command})

    # Send to LLM and process response
    response = send_to_llm(context, **kwargs)
    highlighted_response = apply_syntax_highlighting(response, reindent_with_tabs=llm_config['llm_reindent_with_tabs'])
    if do_slow_print:
        slow_print(highlighted_response)
    else:
        print(highlighted_response)

    # Record the debug history if the option is enabled
    if llm_config['record_debug_history']:
        record_debug_history(context, response)

    update_history("user", command)
    update_history("assistant", response)
    if llm_config['experimental_llm_agent']:
        diff_context = []
        diff_context.extend(context_file_entries)
        diff_context.append({"role": "user", "content": command})
        diff_context.append({"role": "assistant", "content": response})
        diff_context.append({"role": "system", "content": experimental_llm_agent.llm_diff_instruction})
        diff_response = send_to_llm(diff_context)
        print('')
        print('[[edit response:]]')
        print(apply_syntax_highlighting(diff_response, reindent_with_tabs=False))

        for filepath, search_block, replace_block in parse_diff_string(diff_response):
            print(f"Applying changes to {filepath}...")
            apply_changes(filepath, search_block, replace_block)

        # Execute the verifier command after applying changes
        if llm_config['experimental_verifier_command']:
            exit_code = execute_verifier_command(llm_config['experimental_verifier_command'])

def handle_llm_bash_agent_loop(command):
    next_command = command
    while handle_llm_bash_agent_command(next_command) > 0:
        print("\t analyzing the results of the user's request")
        analysis_command = handle_llm_bash_agent_analysis()
        next_command = analysis_command
        print("\t continuing bash agent loop...")
    print("no commands executed, bash agent complete!")

def handle_llm_bash_agent_command(command):
    # Prepare the context
    context = history[-llm_config['llm_history_length']*2:]

    instruction = '''You are a bash agent.
Plan and write the bash commands to be executed in this shell to implement the user's requests.
Anything outside of triple markdown quotes will be ignored.
All bash commands to be executed should within markdown quotes with the type "sh":

```sh
echo asdf > whoami
ls -la
```

Another example:

```sh
echo 'print("Hello, World!")' > hello_world.py
python3 hello_world.py
```

All bash commands will be executed unless a command exits with a non-zero exit code.
Do not use multi-line commands. Only single line commands will execute successfully.
Make sure to add verification commands to check that our executions were successful.
When the user's task is completed, output no commands to indicate a completed job.
'''

    context.append({"role": "system", "content": instruction})
    context.append({"role": "user", "content": command})

    # Send to LLM and process response
    response = send_to_llm(context)
    # highlighted_response = apply_syntax_highlighting(response, reindent_with_tabs=llm_config['llm_reindent_with_tabs'])
    slow_print(response)

    update_history("user", command)
    update_history("assistant", response)

    commands_executed = 0
    for command in parse_bash_string(response):
        commands_executed += 1
        print('executing $', command)
        exit_code = process_standard_command(command)
        if exit_code != 0:
            break
    return commands_executed

def handle_llm_bash_agent_analysis():
    # Prepare the context
    context = history[-llm_config['llm_history_length']*2:]

    instruction = '''You are an analysis tool.
Analyze whether the assistant correct implemented the user's request.
If the request is complete, state it as such. Emphasis that no additional commands should be executed.
If the request is incomplete, write next set of instructions for the bash agent.

Be clear and concise.
Explain what went wrong, explain what went right.
Restate the user's request, and state the next steps to the bash agent.
'''

    context.append({"role": "system", "content": instruction})

    # Send to LLM and process response
    response = send_to_llm(context)
    # highlighted_response = apply_syntax_highlighting(response, reindent_with_tabs=llm_config['llm_reindent_with_tabs'])
    slow_print(response)

    return response
    


def set_file_arg(file_var, *args):
    if len(args) > 0:
        files = [] if len(args) == 1 and args[0].lower() == 'none' else [file for arg in args for file in glob.glob(arg) if file]
        llm_config[file_var] = files
        print(f"{file_var} file(s) set to {files}")
        save_llm_config_to_file(config_path=os.path.join(os.path.expanduser('~'), '.llm_shell_config'), llm_config=llm_config)
    else:
        print(f"{file_var} file(s): {llm_config[file_var]}")

def set_config_arg(module, option, *value, custom_parser=None, censor_value=False):
    if type(module) is dict:
        if len(value) > 0:
            module[option] = ' '.join(value).strip() if not custom_parser else custom_parser(' '.join(value).strip())
            print('set ' + option + ' to', module[option] if not censor_value else '[...]')
            save_llm_config_to_file(config_path=os.path.join(os.path.expanduser('~'), '.llm_shell_config'), llm_config=llm_config)
            if option.startswith('experimental_'):
                print('\t warning: you are setting an experimental option. make sure you know what you\'re doing!')
        else:
            print(option + ':', module[option] if not censor_value else '[...]')
    else:
        if len(value) > 0:
            setattr(module, option, ' '.join(value).strip() if not custom_parser else custom_parser(' '.join(value).strip()))
            print('set ' + option + ' to', getattr(module, option) if not censor_value else '[...]')
            save_llm_config_to_file(config_path=os.path.join(os.path.expanduser('~'), '.llm_shell_config'), llm_config=llm_config)
            if option.startswith('experimental_'):
                print('\t warning: you are setting an experimental option. make sure you know what you\'re doing!')
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
llm-experimental-agent [true/false] - Allows the llm to write/edit files on its own. Beware: highly experimental.
llm-experimental-verifier [./run_unittest.py] - Gives a command to run your unit tests and verify after the llm-agent has completed. Beware: highly experimental.
llm-experimental-bash-agent [true/false] - Runs a looping bash agent with your request. Beware: highly experimental.
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
    'llm-experimental-agent': partial(set_config_arg, llm_config, 'experimental_llm_agent', custom_parser=lambda s: s.lower() == 'true'),
    'llm-experimental-bash-agent': partial(set_config_arg, llm_config, 'experimental_bash_agent', custom_parser=lambda s: s.lower() == 'true'),
    'llm-experimental-verifier': partial(set_config_arg, llm_config, 'experimental_verifier_command'),
    'llm-record-debug-history': partial(set_config_arg, llm_config, 'record_debug_history', custom_parser=lambda s: s.lower() == 'true'),
    'llm-history-length': partial(set_config_arg, llm_config, 'llm_history_length', custom_parser=lambda s: int(s)),
    'llm-chatgpt-apikey': partial(set_config_arg, chatgpt_support, 'chatgpt_api_key', censor_value=True),
    'context': partial(set_file_arg, 'context_file'),
    'summary': partial(set_file_arg, 'summary_file'),
}

def process_standard_command(command):
    output, exit_code = execute_shell_command(command)
    shortened_output = shorten_output(output)
    if exit_code == 0:
        update_history('user', f'$ {command}\n{shortened_output}')
    else:
        update_history('user', f'$ {command}\n{shortened_output}\nexit_code: {exit_code}')
    return exit_code

def handle_command(command):
    cmd_key, *args = command.split(maxsplit=1)
    cmd_key = cmd_key.lower()
    if cmd_key in commands:
        arguments = args[0].split() if args else []
        commands[cmd_key](*arguments)
    elif command.startswith('#'):
        command = command[1:] # Remove the '#'
        if llm_config['experimental_bash_agent']:
            handle_llm_bash_agent_loop(command)
        else:
            handle_llm_command(command, do_slow_print=True)
    else:
        process_standard_command(command)

def autocomplete_string(text, state):
    full_input = readline.get_line_buffer()
    split_input = full_input.split()

    # Custom commands for autocompletion
    custom_commands = [ k + ' ' for k in commands.keys() ]
    # custom_commands = ['llm-backend ', 'llm-instruction ', 'llm-reindent-with-tabs ', 'llm-history-length ', 'llm-chatgpt-apikey ', 'context ', 'summary ']

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
            command = input(get_prompt(llm_config['llm_backend'], llm_config['experimental_llm_agent']))
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

    # Load the LLM config from file
    load_llm_config_from_file(config_path=os.path.join(os.path.expanduser('~'), '.llm_shell_config'), llm_config=llm_config)

    # Start the LLM shell
    run_llm_shell()


def ask_llm():
    # Initialize the argument parser
    parser = argparse.ArgumentParser(description='Ask a question to the LLM.')
    parser.add_argument('-v', '--version', action='version', version='LLM Shell v' + version)
    parser.add_argument('-in', '--stdin', action='store_true', help='Read input from stdin.')
    parser.add_argument('-c', '--context', action='append', default=[], help='Set a file to use as context for the language model.')
    parser.add_argument('topic', nargs='?', default='', help='The topic or question to ask the LLM.')

    # Parse the arguments
    args = parser.parse_args()

    # Read available stdin if --stdin is provided
    if args.stdin:
        stdin_content = sys.stdin.read()
    else:
        stdin_content = ''

    # Prepare the context
    query = ''
    if stdin_content:
        query += stdin_content + "\n\n\n"
    if args.topic:
        query += args.topic

    if not (stdin_content or args.topic):
        print("No input provided. Please provide a topic or question, or pipe some input to the command with --stdin.")
        return

    # Load the LLM config from file
    load_llm_config_from_file(config_path=os.path.join(os.path.expanduser('~'), '.llm_shell_config'), llm_config=llm_config)

    # Set the context_file from the -c/--context arguments
    llm_config['context_file'] = args.context

    response = handle_llm_command(query, show_spinner=False)
    print(response)

