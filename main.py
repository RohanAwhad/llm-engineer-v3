import aiofiles
import argparse
import asyncio
import sys

from loguru import logger
from pathlib import Path
from pydantic_ai import Agent, UnexpectedModelBehavior
from traceloop.sdk.decorators import workflow, task

from src.logger import setup_logging
setup_logging()

from src import file_writer, dir_structure_retriever

# --- Agent Definition ---

agent_system_prompt = f"""
You are an AI software developer agent operating within a local file system repository.
Your goal is to understand user requests for code changes, feature implementations, or bug fixes,
and then execute them using the available tools.

Follow this workflow:
1.  **Analyze & Understand:** Carefully read the user's query. Use the `read_file` tool to examine relevant existing files and the `grep` tool to search for specific code patterns, functions, or variables if needed to understand the context.
2.  **Plan:** Based on your analysis, create a clear, step-by-step plan. Outline which files need to be created or modified, and what specific changes are required. If any shell commands are needed (e.g., running tests, installing dependencies), include them in the plan.
3.  **Execute:** Implement the plan using the available tools:
    *   `read_file(file_path_str: str)`: Reads the content of a specified file.
    *   `grep(pattern: str, directory_str: str = ".")`: Searches for a pattern in files within a directory (defaults to current).
    *   `apply_patch_to_file(file_path_str: str, new_content: str)`: **IMPORTANT:** Use this to modify files. Provide the *complete, final content* for the file in the `new_content` argument. This tool will overwrite the existing file or create a new one. Generate the full file content based on your plan.
    *   `run_bash_command(command: str)`: Executes a shell command. **Crucially, you MUST use this tool for any shell command execution. The user will be prompted for confirmation before the command runs.** Explain *why* the command is needed when you call this tool.
    *   `ask_human_for_help(question: str)`: Use this tool when you need input or clarification from the human. The question will be presented to the user and their response will be returned.
4.  **Summarize:** After executing the plan, provide a concise summary of the actions taken (files changed, commands run) and the overall outcome of the request. This summary will be your final output.

Constraints:
- Only interact with the file system and execute commands using the provided tools.
- **ALWAYS ask for permission via the `run_bash_command` tool before executing any shell command.** Do not try to execute commands directly.
- When using `apply_patch_to_file`, ensure the `new_content` argument contains the *entire* intended content of the file after the changes.
- Work relative to the current working directory unless specified otherwise.
- Be methodical and break down complex tasks into smaller steps.
- Use the `ask_human_for_help` tool whenever you need user input or clarification.

Here's the current directory structure:
{dir_structure_retriever.tree_command()}
""".strip()


agent = Agent(
    model='google-gla:gemini-2.5-pro-preview-03-25',
    system_prompt=agent_system_prompt,
    instrument=True,
)

# --- Tool Implementations ---

@task()
@agent.tool_plain()
async def run_bash_command_impl(command: str) -> str:
    """
    Executes a bash command after getting user confirmation.

    Args:
        command: The bash command to execute.

    Returns:
        A string containing the stdout and stderr of the command execution,
        or an error message if execution fails or is denied.
    """
    logger.info(f"Requesting permission to run command: {command}")
    try:
        # Get user confirmation synchronously within the async function
        # Note: This blocks the event loop, but is acceptable for simple user interaction.
        # For more complex scenarios (e.g., GUI), use a different approach.
        confirm = input(f"Allow execution of command? [y/N]: '{command}'\n> ").strip().lower()
        if confirm != 'y':
            logger.warning("User denied command execution.")
            return "Command execution denied by user."

        logger.info(f"Executing command: {command}")
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        output = f"Command: {command}\n"
        output += f"Return Code: {process.returncode}\n"
        if stdout:
            output += f"STDOUT:\n{stdout.decode().strip()}\n"
            logger.debug(f"Command STDOUT: {stdout.decode().strip()}")
        if stderr:
            output += f"STDERR:\n{stderr.decode().strip()}\n"
            logger.warning(f"Command STDERR: {stderr.decode().strip()}")

        return output

    except Exception as e:
        logger.error(f"Failed to execute command '{command}': {e}")
        return f"Error executing command '{command}': {e}"


@task()
@agent.tool_plain()
async def read_file_impl(file_path_str: str) -> str:
    """
    Reads the content of a file asynchronously.

    Args:
        file_path_str: The path to the file to read.

    Returns:
        The content of the file as a string, or an error message
        if the file cannot be read.
    """
    file_path = Path(file_path_str)
    logger.info(f"Reading file: {file_path}")
    try:
        async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
            content = await f.read()
        logger.debug(f"Successfully read {len(content)} characters from {file_path}")
        return content
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return f"Error: File not found at path '{file_path_str}'"
    except Exception as e:
        logger.error(f"Failed to read file '{file_path}': {e}")
        return f"Error reading file '{file_path_str}': {e}"


@task()
@agent.tool_plain()
async def grep_impl(pattern: str, directory_str: str = ".") -> str:
    """
    Searches for a pattern within files in a specified directory using grep.

    Args:
        pattern: The pattern to search for (can be a regex).
        directory_str: The directory to search within (defaults to current directory).

    Returns:
        The output of the grep command, or an error message.
    """
    directory = Path(directory_str)
    if not directory.is_dir():
        logger.error(f"Grep target is not a valid directory: {directory}")
        return f"Error: '{directory_str}' is not a valid directory."

    # Basic grep command - might need refinement for specific needs (e.g., recursive, ignore case)
    # Using -r for recursive, -n for line numbers, -I to ignore binary files
    command = f"grep -r -n -I '{pattern}' {directory.resolve()}"
    logger.info(f"Running grep: {command}")

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        output = f"Grep Command: {command}\n"
        output += f"Return Code: {process.returncode}\n" # Grep returns 1 if no lines selected, 0 if lines selected, >1 for errors
        if stdout:
            results = stdout.decode().strip()
            output += f"Results:\n{results}\n"
            logger.debug(f"Grep results found for pattern '{pattern}'")
        else:
             output += "Results: No matches found.\n"
             logger.debug(f"Grep: No matches found for pattern '{pattern}'")

        if stderr:
            error_msg = stderr.decode().strip()
            # Ignore common "Permission denied" errors for brevity unless debugging
            if "Permission denied" not in error_msg:
                 output += f"STDERR:\n{error_msg}\n"
                 logger.warning(f"Grep STDERR: {error_msg}")
            else:
                 logger.debug(f"Grep STDERR (Permission Denied Ignored): {error_msg}")


        return output

    except Exception as e:
        logger.error(f"Failed to run grep command '{command}': {e}")
        return f"Error running grep for pattern '{pattern}': {e}"


@task()
@agent.tool_plain()
async def apply_patch_to_file_impl(file_path_str: str, new_content: str):
    """
    Writes the provided `new_content` to the specified `file_path`.
    If the file exists, it will be overwritten. If it doesn't exist, it will be created.
    This assumes the LLM generates the complete, final content for the file.

    Args:
        file_path_str: The path to the file to write to.
        new_content: The full content to write to the file.
    """
    await file_writer.apply_patch_to_file(Path(file_path_str), new_content)


@task()
@agent.tool_plain()
async def ask_human_for_help_impl(question: str) -> str:
    """
    Asks the human user for help or input on a specific question.

    Args:
        question: The question or request for clarification to ask the human.

    Returns:
        The human's response as a string.
    """
    logger.info(f"Asking human for help: {question}")
    try:
        # Present the question to the user and get their input
        response = input(f"\n[Agent is asking]: {question}\n> ")
        logger.debug(f"Human provided response: {response[:100]}...")
        return response
    except Exception as e:
        logger.error(f"Error while asking human for help: {e}")
        return f"Error obtaining user input: {e}"


# --- Main Execution Logic ---

@workflow(name='coder')
async def process_request(user_query: str):
    """Processes the user's request using the agent."""
    logger.info(f"Received user query: '{user_query[:100]}...'")
    logger.info("Running agent...")
    try:
        result = await agent.run(user_query)
        logger.success("Agent finished successfully.")
        print("\n--- Agent Summary ---")
        print(result.output)
        print("---------------------\n")
    except UnexpectedModelBehavior as e:
        logger.error(f"Agent run failed: {e}")
        print(f"\n--- Agent Error ---\n{e}\n-------------------\n", file=sys.stderr)
    except Exception as e:
        logger.exception("An unexpected error occurred during agent execution.")
        print(f"\n--- Unexpected Error ---\n{e}\n----------------------\n", file=sys.stderr)


async def main():
    """Parses arguments and runs the agent processing."""
    parser = argparse.ArgumentParser(
        description="AI Software Developer Agent CLI. Provide a prompt directly or via a file."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "direct_prompt",
        nargs="?",  # Makes it optional within the group
        type=str,
        help="The development task/instruction for the agent.",
    )
    group.add_argument(
        "-p",
        "--prompt-file",
        type=Path,
        help="Path to a file containing the prompt for the agent.",
    )

    args = parser.parse_args()

    user_prompt = ""
    if args.direct_prompt:
        user_prompt = args.direct_prompt
    elif args.prompt_file:
        try:
            prompt_path = args.prompt_file.resolve()
            logger.info(f"Reading prompt from file: {prompt_path}")
            with open(prompt_path, "r", encoding="utf-8") as f:
                user_prompt = f.read()
        except FileNotFoundError:
            logger.error(f"Prompt file not found: {args.prompt_file}")
            sys.exit(f"Error: Prompt file not found at '{args.prompt_file}'")
        except Exception as e:
            logger.error(f"Error reading prompt file {args.prompt_file}: {e}")
            sys.exit(f"Error reading prompt file: {e}")

    if not user_prompt:
        logger.error("No prompt provided.")
        parser.print_help()
        sys.exit(1)

    await process_request(user_prompt)


def cli_entrypoint():
    """Entry point for the CLI tool."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
        sys.exit(0)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
        sys.exit(0)
