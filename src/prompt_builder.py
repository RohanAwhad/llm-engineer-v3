import os
import fnmatch


def get_non_gitignore_files() -> list[str]:
  """
  Get a list of all files in the current directory recursively,
  excluding those that match patterns in .gitignore
  """

  # Default list of files to consider
  all_files = []

  # Traverse directory tree
  for root, _, files in os.walk('.'):
    # Skip .git directory
    if '.git' in root.split(os.path.sep):
      continue

    for file in files:
      file_path = os.path.join(root, file)
      # Make path relative to current directory
      rel_path = os.path.relpath(file_path, '.')
      all_files.append(rel_path)

  # Check if .gitignore exists
  if not os.path.exists('.gitignore'):
    return [f for f in all_files if not f.endswith('.lock')]

  # Read .gitignore
  with open('.gitignore', 'r') as gitignore_file:
    gitignore_patterns = [line.strip() for line in gitignore_file if line.strip() and not line.startswith('#')]

  # Filter out files that match gitignore patterns
  non_gitignore_files = []
  for file_path in all_files:
    # Skip .lock files
    if file_path.endswith('.lock'):
      continue

    should_ignore = False
    for pattern in gitignore_patterns:
      # Handle negation pattern (starts with !)
      is_negation = pattern.startswith('!')
      if is_negation:
        pattern = pattern[1:]

      # Handle directory-specific pattern (ends with /)
      is_dir_only = pattern.endswith('/')
      if is_dir_only:
        pattern = pattern[:-1]
        if not os.path.isdir(file_path):
          continue

      # Convert gitignore pattern to fnmatch pattern
      if pattern.startswith('/'):
        # Pattern that starts with / matches only files in root
        pattern = pattern[1:]
        match = fnmatch.fnmatch(file_path, pattern)
      elif '/' in pattern:
        # Pattern with / matches relative to repo root
        match = fnmatch.fnmatch(file_path, pattern)
      else:
        # Pattern matches anywhere in path
        match = fnmatch.fnmatch(file_path, f"*{pattern}*")

      # Apply the match result based on whether it's a negation
      if match and not is_negation:
        should_ignore = True
        break
      elif match and is_negation:
        should_ignore = False
        break

    if not should_ignore:
      non_gitignore_files.append(file_path)

  return non_gitignore_files


def get_file_content(file_path: str) -> str:
  """
  Read and return the content of a file

  Args:
    file_path: Path to the file to read

  Returns:
    The content of the file as a string
  """
  try:
    with open(file_path, 'r', encoding='utf-8') as file:
      return file.read().strip()
  except UnicodeDecodeError:
    # If we can't read as utf-8, try binary mode
    try:
      with open(file_path, 'rb') as file:
        return "[Binary file not shown]"
    except Exception as e:
      return f"[Error reading file: {str(e)}]"
  except Exception as e:
    return f"[Error reading file: {str(e)}]"


def runner(problem: str) -> str:
  """
  Creates an XML-like string containing all non-gitignored files and their contents

  Returns:
    A string in the format:
    <files>
        <file>
            <filepath>path/to/file</filepath>
            <content>file content here</content>
        </file>
        ...
    </files>
  """
  files = get_non_gitignore_files()
  result = ""

  for file_path in files:
    content = get_file_content(file_path)
    result += "  <file>\n"
    result += f"    <filepath>{file_path}</filepath>\n"
    result += f"    <content>{content}</content>\n"
    result += "  </file>\n"

  system_prompt = f'''
I am using you as a prompt generator. I've dumped the entire context of my code base, and I have a specific problem. Please come up with a proposal to my problem - including the code and general approach.

<files>
{result}
</files>

<problem>
{problem}
</problem>

Please make sure that you leave no details out, and follow my requirements specifically. I know what I am doing, and you can assume that there is a reason for my arbitrary requirements. 

When generating the full prompt with all of the details, keep in mind that the model you are sending this to is not as intelligent as you. It is great at very specific instructions, so please stress that they are specific. 

Come up with discrete steps such that the sub-llm i am passing this to can build intermediately; as to keep it on the rails. Make sure to stress that it stops for feedback at each discrete step.
  '''.strip()

  return system_prompt



if __name__ == '__main__':
  import pyperclip
  problem = '''
I want to add a new cli argument for prompt builder. It should basically take in a problem, and run the prompt builder runner to get the final prompt. Then it should use pyperclip.copy() to copy it to clipboard.
  '''.strip()
  pyperclip.copy(runner(problem))

