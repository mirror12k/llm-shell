import os
import os.path
import re
import getpass
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import TerminalFormatter
import threading
import time
import json



def read_file_contents(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
        return None

def color_text(text, color_code):
    ANSI_RESET = '\033[0m'  # Reset all attributes
    return f"\001{color_code}\002{text}\001{ANSI_RESET}\002"

def bold_gold(text):
    ANSI_BOLD = '\033[1m'  # Bold
    ANSI_GOLD = '\033[33m'  # Gold color
    return color_text(text, ANSI_BOLD + ANSI_GOLD)

def bold_red_and_black_background(text):
    ANSI_BLACK_BG = '\033[40m'    # Black Background
    ANSI_BOLD_RED = '\033[1;31m'  # Bold Red
    return color_text(text, ANSI_BLACK_BG + ANSI_BOLD_RED)

# Function to generate the prompt
def get_prompt(llm_backend, llm_agent):
    user = getpass.getuser()
    cwd = os.getcwd()
    if llm_agent:
        return f"{user}:{cwd} {bold_red_and_black_background(f'AGENT<<{llm_backend}>>')}$ "
    else:
        return f"{user}:{cwd} {bold_red_and_black_background(f'<<{llm_backend}>>')}$ "


def shorten_output(output):
    if len(output) > 2000:
        return output[:1000] + '\n...\n' + output[-1000:]
    else:
        return output

def summarize_file(text):
    return re.sub(r'(\t# \.\.\.\n?)+', '\t# ...\n', '\n'.join(line if not re.match(r'^\s+', line) else '\t# ...' for line in text.split('\n') if not re.match(r'^(\s*$|\s*#.*|\s*//.*)', line)))

def apply_syntax_highlighting(response, reindent_with_tabs=False):
    # Regex to find code blocks with optional language specification
    code_block_regex = r"```(\w+)?\n(.*?)\n```"
    matches = re.finditer(code_block_regex, response, re.DOTALL)

    highlighted_response = response
    for match in matches:
        language = match.group(1) if match.group(1) else "text"
        code = match.group(2)
        
        # If reindent_with_tabs is True, convert four leading spaces to tabs
        if reindent_with_tabs:
            code = re.sub(r'(?m)^( {4})+', lambda x: '\t' * (len(x.group(0)) // 4), code)
        
        try:
            lexer = get_lexer_by_name(language, stripall=True)
            formatter = TerminalFormatter()
            highlighted_code = highlight(code, lexer, formatter)
            highlighted_response = highlighted_response.replace(match.group(0), f'```\n{highlighted_code}\n```')
        except Exception:
            pass  # If language not found, leave the code block as is

    return highlighted_response

def spinner(id, stop):
    spinner_chars = "|/-\\"
    idx = 0
    while not stop():  # Use the global flag to keep spinning
        print(spinner_chars[idx % len(spinner_chars)], end='\r')
        idx += 1
        time.sleep(0.1)
    print(' ', end='\r')

class BarSpinner:
    def __enter__(self):
        self.stop_threads = False
        self.spinner_thread = threading.Thread(target=spinner, args=(id, lambda: self.stop_threads))
        self.spinner_thread.start()
        # return lambda: end_spinner(spinner_thread) 

    def __exit__(self, exception_type, exception_value, traceback):
        self.stop_threads = True
        self.spinner_thread.join()  # Wait for the spinner thread to finish

# stop_threads = False
def start_spinner():
    return BarSpinner()

def slow_print(msg, over_time=2):
    # Print the highlighted_response progressively over N seconds
    total_time = over_time # total time to print the message
    num_chars = len(msg)
    delay_per_char = min(total_time / num_chars, 0.01)

    for char in msg:
        print(char, end='', flush=True)
        time.sleep(delay_per_char)
    print('')

def parse_diff_string(diff_string):
    # Define a regex pattern to match the whole block of text for each file
    pattern = re.compile(r'(`?)([^\n]*?)\1\n'  # Match the file path
                         r'```(?:.*?)\n'           # Match the start fence
                         r'<<<<<<< SEARCH\n'              # Match the start of the search block
                         r'(.*?)\n?'                        # Capture the search content
                         r'=======\n'                      # Match the divider
                         r'(.*?)\n?'                        # Capture the replace content
                         r'>>>>>>> REPLACE\n+',              # Match the end of the replace block
                         # r'```',                 # Match the end fence
                         re.DOTALL)                        # DOTALL flag to match across newlines

    # Find all matches in the input string
    matches = pattern.findall(diff_string)

    # Extract the file path, search string, and replace string from each match
    diff_data = []
    for match in matches:
        file_path = match[1].strip()
        search_string = match[2].strip()
        replace_string = match[3].strip()
        diff_data.append((file_path, search_string, replace_string))

        if '\n=======\n' in search_string:
            print("[!!!] this doesn't look correct:", search_string)

    return diff_data

def apply_changes(filepath, search_block, replace_block):
    # Read the current contents of the file
    if os.path.isfile(filepath):
        with open(filepath, 'r') as file:
            file_contents = file.read()
    else:
        file_contents = ''

    # Replace the search block with the replace block
    if search_block in file_contents:
        file_contents = file_contents.replace(search_block, replace_block, 1)
    else:
        print(f"Search block {{ {search_block} }} not found in '{filepath}'. No changes made.")
        return False

    # Write the modified contents back to the file
    with open(filepath, 'w') as file:
        file.write(file_contents)
    print(f"Changes applied to '{filepath}'.")
    return True

def save_llm_config_to_file(config_path, llm_config):
    try:
        with open(config_path, 'w') as config_file:
            json.dump(llm_config, config_file, indent=4)
        # print(f"Config saved to {config_path}")
    except Exception as e:
        pass
        # print(f"Error saving config to {config_path}: {e}")

def load_llm_config_from_file(config_path, llm_config):
    try:
        with open(config_path, 'r') as config_file:
            loaded_config = json.load(config_file)
            for key, value in loaded_config.items():
                if key in llm_config:
                    llm_config[key] = value
            # print(f"Config loaded from {config_path}")
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as e:
        print(f"Error decoding the config file at {config_path}: {e}")
    except Exception as e:
        print(f"Error loading config from {config_path}: {e}")

def record_debug_history(context, response):
    debug_history_path = os.path.join(os.path.expanduser('~'), '.llm_shell_debug_history')
    debug_entry = {
        'context': context,
        'response': response
    }
    with open(debug_history_path, 'a') as debug_file:
        json.dump(debug_entry, debug_file)
        debug_file.write('\n') # Write a newline to separate entries
