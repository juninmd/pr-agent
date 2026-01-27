import os
import pytest

MAX_LINES = 150

def get_line_count(filepath):
    with open(filepath, 'r') as f:
        return sum(1 for _ in f)

@pytest.mark.parametrize("filepath", [
    "pr_agent/tools/pr_code_agent.py",
    "pr_agent/tools/code_agent/tools.py",
    "pr_agent/tools/code_agent/tool_registry.py",
    "pr_agent/tools/code_agent/prompts.py",
    "pr_agent/tools/code_agent/diff_utils.py",
])
def test_file_line_count(filepath):
    """
    Verify that the 'Jules' agent files are under 150 lines of code
    to adhere to Clean Code, SRP, and KISS principles.
    """
    if not os.path.exists(filepath):
        pytest.fail(f"File not found: {filepath}")

    line_count = get_line_count(filepath)
    assert line_count < MAX_LINES, f"{filepath} has {line_count} lines, exceeding the limit of {MAX_LINES}"
