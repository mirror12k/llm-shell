import os
import re
import getpass
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import TerminalFormatter
import threading
import time



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
def get_prompt(llm_backend):
    user = getpass.getuser()
    cwd = os.getcwd()
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

