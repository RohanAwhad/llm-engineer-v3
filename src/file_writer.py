import asyncio
import argparse
import re
from pathlib import Path
from typing import Optional

from pydantic_ai import Agent
from loguru import logger

# --- Agent Configuration ---

# Define the system prompt for the code patching agent


AGENT_SYSTEM_PROMPT = """
You are an expert code generation assistant. Your task is to apply a given patch or set of instructions to an existing piece of code (or generate code for a new file).

You will receive the original code (if any) and the patch instructions.

**CRITICAL INSTRUCTIONS:**
1.  **Apply the Patch:** Modify the original code according to the patch instructions.
2.  **Resolve Placeholders:** If the patch contains placeholders like "TODO: Implement logic", "Write your logic here", "Same as before", or similar instructional comments, you MUST infer the intended code based on the context and generate the actual implementation. **DO NOT simply copy the placeholder text into the final code.**
3.  **Generate Complete Code:** Output the *entire* final code content for the file after applying the patch and resolving placeholders.
4.  **Output Format:** Enclose the complete, final code block *strictly* within <code> and </code> tags. Do not include *any* other text, explanations, or markdown formatting outside these tags.

Example:
<input_code>
def calculate_area(length, width):
    # TODO: Calculate area
    pass
</input_code>
<patch>
@@ -1,3 +1,2 @@
 def calculate_area(length, width):
-    # TODO: Calculate area
-    pass
+    return length * width
<patch>

Expected Output:
<code>
def calculate_area(length, width):
    return length * width
</code>
""".strip()


# Initialize the Pydantic AI Agent
code_patcher_agent = Agent(
    model='google-gla:gemini-2.0-flash',
    system_prompt=AGENT_SYSTEM_PROMPT,
)

# --- Core Logic ---

async def apply_patch_to_file(file_path: Path, patch: str):
    """
    Reads a file, applies a patch using an LLM, and writes the result back.

    Handles placeholder comments in the patch by generating actual code.
    If the file doesn't exist, it creates it with the patched content.
    """
    logger.info(f"Processing file: {file_path}")
    logger.info(f"Applying patch: {patch}")

    original_content: Optional[str] = None
    try:
        original_content = file_path.read_text()
        logger.info(f"Read existing content from {file_path}")
    except FileNotFoundError:
        logger.warning(f"File not found: {file_path}. Will create a new file. and write the patch directly to it.")
        original_content = None # Explicitly None for clarity

    # Prepare the prompt for the LLM
    if original_content:
        prompt = f"<input_code>\n{original_content.strip()}\n</input_code>\n\nApply the following patch to the code above.\n\n<patch>\n{patch}\n</patch>"

        logger.debug("Sending request to LLM...")
        try:
            result = await code_patcher_agent.run([prompt])
            raw_output = result.output
            logger.debug(f"LLM Raw Output:\n{raw_output}")

            # Parse the code from the <code> block
            match = re.search(r'<code>(.*?)</code>', raw_output, re.DOTALL | re.IGNORECASE)
            if not match:
                logger.error("Could not parse code from LLM response. No <code> block found.")
                logger.error(f"LLM Response was: {raw_output}")
                return

            final_code = match.group(1).strip()
        except Exception as e:
            logger.exception(f"An error occurred during LLM processing: {e}")
            # Consider more specific exception handling if needed
            return
    else:
        final_code = patch

    # Write the final code to the file
    file_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
    file_path.write_text(final_code)
    logger.success(f"Successfully applied patch and wrote to {file_path}")
    logger.info(f"Final Code written:\n```\n{final_code}\n```") # Log snippet for verification


# --- Command Line Interface ---

async def main():
    parser = argparse.ArgumentParser(description="Apply patches to files using an LLM, intelligently handling placeholders.")
    parser.add_argument("file_path", type=str, help="Path to the file to be patched.")
    parser.add_argument("patch", type=str, help="The patch instructions or description.")
    args = parser.parse_args()

    file_path = Path(args.file_path)
    await apply_patch_to_file(file_path, args.patch)

if __name__ == "__main__":
    # Configure Loguru
    logger.add("code_patcher.log", rotation="1 MB") # Log to a file
    logger.info("Starting code patcher script...")

    # Make sure GEMINI_API_KEY environment variable is set
    import os
    if not os.getenv("GEMINI_API_KEY"):
        logger.exception("GEMINI_API_KEY environment variable not set. LLM calls may fail.")
        exit(1)

    asyncio.run(main())
    logger.info("Script finished.")
