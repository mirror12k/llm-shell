import os
import re
import getpass
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import TerminalFormatter



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
def get_prompt(llm_backend):
    user = getpass.getuser()
    cwd = os.getcwd()
    return f"{user}:{cwd} {bold_red_and_black_background(f'<<{llm_backend}>>')}$ "


def shorten_output(output):
    if len(output) > 2000:
        return output[:1000] + '\n...\n' + output[-1000:]
    else:
        return output

def change_directory(target_dir):
    """Change the current working directory."""
    try:
        os.chdir(target_dir)
        return ""
    except OSError as e:
        return str(e)

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
