#!/usr/bin/env python3
import sys
import os
import subprocess
import getpass
import requests
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import TerminalFormatter
import re
import readline
import glob
import traceback

# Global flag to indicate if a command is currently running
is_command_running = False
llm_backend = os.getenv('LLM_BACKEND', 'gpt-4-turbo')
chatgpt_api_key = os.getenv('CHATGPT_API_KEY')
context_file = None
history = []  # Initialize an empty list for context history

def color_text(text, color_code):
    ANSI_RESET = '\033[0m'  # Reset all attributes
    return f"{color_code}{text}{ANSI_RESET}"

def bold_gold(text):
    ANSI_BOLD = '\033[1m'  # Bold
    ANSI_GOLD = '\033[33m'  # Gold color
    return color_text(text, ANSI_BOLD + ANSI_GOLD)

def bold_red_and_black_background(text):
    ANSI_BLACK_BG = '\033[40m'    # Black Background
    ANSI_BOLD_RED = '\033[1;31m'  # Bold Red
    return color_text(text, ANSI_BLACK_BG + ANSI_BOLD_RED)

# Function to generate the prompt
def get_prompt():
    user = getpass.getuser()
    cwd = os.getcwd()
    return f"{user}:{cwd} {bold_red_and_black_background(f'<<{llm_backend}>>')}$ "


def shorten_output(output):
    if len(output) > 2000:
        return output[:1000] + '\n...\n' + output[-1000:]
    else:
        return output

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
        # print("\nCommand interrupted.")
    finally:
        is_command_running = False

    return ''.join(output)


def apply_syntax_highlighting(response):
    # Regex to find code blocks with optional language specification
    code_block_regex = r"```(\w+)?\n(.*?)\n```"
    matches = re.finditer(code_block_regex, response, re.DOTALL)

    highlighted_response = response
    for match in matches:
        language = match.group(1) if match.group(1) else "text"
        code = match.group(2)
        try:
            lexer = get_lexer_by_name(language, stripall=True)
            formatter = TerminalFormatter()
            highlighted_code = highlight(code, lexer, formatter)
            highlighted_response = highlighted_response.replace(match.group(0), f'```\n{highlighted_code}\n```')
        except Exception:
            pass  # If language not found, leave the code block as is

    return highlighted_response

def change_directory(target_dir):
    """Change the current working directory."""
    try:
        os.chdir(target_dir)
        return ""
    except OSError as e:
        return str(e)

def send_to_gpt4turbo(context):
    return send_to_chatgpt_model(context, 'gpt-4-1106-preview')

def send_to_gpt4(context):
    return send_to_chatgpt_model(context, 'gpt-4')

def send_to_gpt35turbo(context):
    return send_to_chatgpt_model(context, 'gpt-3.5-turbo-1106')


total_estimated_cost = 0
total_tokens_used = 0

model_prices = {
    'gpt-4-1106-preview': { 'output': 0.03, 'input': 0.01 },
    'gpt-4': { 'output': 0.06, 'input': 0.03 },
    'gpt-3.5-turbo-1106': { 'output': 0.0020, 'input': 0.0010 },
}
def send_to_chatgpt_model(context, model):
    global total_estimated_cost, total_tokens_used, chatgpt_api_key

    if not chatgpt_api_key:
        raise Exception("Can't execute chatgpt without 'CHATGPT_API_KEY' environment variable set.")

    headers = {
        "Authorization": f"Bearer {chatgpt_api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": model,
        "messages": [{ "role": "system", "content": "You are a programming assistant. Help the user build programs and resolve errors." }] + context,
        "temperature": 0.7,
        "max_tokens": 1000
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", json=data, headers=headers)


    if response.status_code == 200:
        response_data = response.json()
        # Calculate the estimated cost based on input and output tokens
        estimated_cost_input = response_data['usage']['prompt_tokens'] * model_prices[model]['input'] / 1000
        estimated_cost_output = response_data['usage']['completion_tokens'] * model_prices[model]['output'] / 1000
        total_estimated_cost += estimated_cost_input + estimated_cost_output
        total_tokens_used += response_data['usage']['total_tokens']

        print(f"\t(Total tokens so far: {bold_gold(str(total_tokens_used))}, Total cost so far: {bold_gold(f'${total_estimated_cost:.2f}')} )")

        assistant_message = response_data['choices'][0]['message']['content']
        return assistant_message.strip()
    else:
        return f"Error: {response.status_code}, {response.text}"

def send_to_llm(context):
    if llm_backend == 'gpt-4-turbo':
        return send_to_gpt4turbo(context)
    elif llm_backend == 'gpt-4':
        return send_to_gpt4(context)
    elif llm_backend == 'gpt-3.5-turbo':
        return send_to_gpt35turbo(context)
    else:
        # Placeholder for other LLM backends
        print(f"LLM backend '{llm_backend}' is not supported yet.")
        return "Unsupported LLM backend."

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
        command = command[1:]  # Remove the '#'

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

def shell():
    # Set the tab completion function
    readline.set_completer(complete)
    readline.parse_and_bind('tab: complete')

    while True:
        try:
            sys.stdin.flush()
            command = input(get_prompt())

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
    shell()

if __name__ == "__main__":
    main()
