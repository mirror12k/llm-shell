# LLM-Shell: Language Model Enhanced Command Line Interface

## Overview
LLM-Shell is a command-line interface (CLI) tool that enhances your shell experience with the power of large language models (LLMs) such as GPT-4 and GPT-3.5 Turbo. It acts as a wrapper around your standard shell, allowing you to execute regular shell commands while also providing the capability to consult an LLM for programming assistance, code examples, and executing commands with natural language understanding.

## Features
- Execute standard shell commands with real-time output.
- Use language models to process commands described in natural language.
- Syntax highlighting for code blocks returned by the language model.
- Set one or multiple context/summary files to provide additional information to the LLM.
- Change the underlying LLM backend (e.g., GPT-4 Turbo, GPT-4, GPT-3.5 Turbo).
- Set or update the instruction for the LLM to change how it assists you.
- Autocompletion for custom commands and file paths.
- History tracking of commands and LLM responses.

## Prerequisites
- Python 3
- `requests` library for making HTTP requests to the LLM API.
- `pygments` library for syntax highlighting.
- An API key from OpenAI for accessing their language models.

## Installation

There are two ways to install LLM-Shell:

### Using pip (Recommended)

1. Ensure you have Python 3 installed on your system.
2. Install the `llm-shell` package from PyPI:
   ```
   pip install llm-shell
   ```
3. Set your OpenAI API key as an environment variable `CHATGPT_API_KEY` or within a `.env` file that the script can read.

### Using Git Clone (For Developers)

1. Clone the repository to your local machine.
2. Navigate to the cloned directory.
3. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```
4. Make sure the script is executable:
   ```sh
   chmod +x llm-shell.py
   ```

## Usage

### If Installed Through pip

To start the LLM-Shell, run the following command:

```sh
llm-shell
```
### If Installed By Git Cloning the Repository

To start the LLM-Shell, navigate to the `bin` directory and run the `llm_shell` script:

```sh
./bin/llm_shell
```
### Executing Commands

- Standard shell commands are executed as normal, e.g., `ls -la`.
- To use the LLM, prefix your command with a hash `#`, followed by the natural language instruction, e.g., `# How do I list all files in the current directory?`.

### Special Commands

- `help` - Displays a list of available custom commands within the LLM-Shell.
- `llm-backend [backend]` - Changes the LLM backend. Replace `[backend]` with one of the supported backends (e.g., `gpt-4-turbo`, `gpt-4`, `gpt-3.5-turbo`, `claude-instant-v1`, `claude-v2.1`).
- `llm-instruction [instruction]` - Sets or updates the instruction for the LLM. Use this command to change how the LLM assists you.
- `llm-reindent-with-tabs [true/false]` - Controls auto-reindent with tabs, to help when the LLM doesn't auto-detect it properly.
- `llm-chatgpt-apikey [apikey]` - Set API key for OpenAI's models.
- `context [filename1] [filename2] ...` - Sets one or multiple context files that will be used to provide additional information to the LLM. Use `context none` to clear the context files.
- `summary [filename1] [filename2] ...` - Sets one or multiple summary files. Similar to `context`, but it will summarize the file before sending it to the LLM. Useful if you just want to send an outline of a class instead of the entire code.
- `exit` - Exits LLM-Shell.

### Autocompletion

- The LLM-Shell supports autocompletion for file paths and custom commands. Press `Tab` to autocomplete the current input.

## Customization

Modify the `llm-shell.py` script to add new features or change existing behavior to better suit your needs.

## License

LLM-Shell is released under the MIT License. See the LICENSE file for more information.

## Disclaimer

LLM-Shell is not an official product and is not affiliated with OpenAI.
It's just an open-source tool developed to showcase the integration of LLMs into a command-line environment.
Use it at your own risk.
