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


def test_agent_prompts_content():
    """
    Verify that the 'Jules' agent system prompt contains the specific
    constraints regarding Clean Code, DRY, SRP, KISS, and the 150-line limit.
    """
    from pr_agent.config_loader import get_settings

    system_prompt = get_settings().get("pr_code_agent.system_prompt", "")

    assert "Jules" in system_prompt, "System prompt should mention 'Jules'"
    assert "Clean Code" in system_prompt, "System prompt should mention 'Clean Code'"
    assert "DRY" in system_prompt, "System prompt should mention 'DRY'"
    assert "SRP" in system_prompt, "System prompt should mention 'SRP'"
    assert "KISS" in system_prompt, "System prompt should mention 'KISS'"
    assert "150 lines" in system_prompt, "System prompt should mention the 150-line limit"
    assert "GitLab and GitHub" in system_prompt, "System prompt should mention integration with GitLab and GitHub"
