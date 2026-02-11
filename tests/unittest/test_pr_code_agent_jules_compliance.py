import os
import pytest
from pr_agent.config_loader import get_settings
from pr_agent.tools.pr_code_agent import PRCodeAgent

def test_jules_persona_prompts_strict():
    """
    Verify that the system prompt strictly defines the 'Jules' persona and its core directives.
    This ensures adherence to Clean Code, DRY, SRP, KISS, and strict file limits.
    """
    system_prompt = get_settings().get("pr_code_agent.system_prompt", "")

    # Core Persona Identity
    assert "Jules" in system_prompt, "System prompt must identify the agent as 'Jules'"
    assert "autonomous software engineer" in system_prompt, "System prompt must define the agent's role"

    # Core Principles
    assert "Clean Code" in system_prompt, "System prompt must mention Clean Code"
    assert "DRY" in system_prompt, "System prompt must mention DRY"
    assert "SRP" in system_prompt, "System prompt must mention SRP"
    assert "KISS" in system_prompt, "System prompt must mention KISS"

    # Strict Constraints
    assert "150 lines" in system_prompt, "System prompt must enforce the 150-line limit"
    assert "refactor" in system_prompt, "System prompt must instruct to refactor if limits are exceeded"

    # Integration Context
    assert "GitLab" in system_prompt, "System prompt must mention GitLab integration"
    assert "GitHub" in system_prompt, "System prompt must mention GitHub integration"

def test_jules_toolset_registration_strict():
    """
    Verify that the PRCodeAgent registers the complete set of tools available to 'Jules'.
    """
    from unittest.mock import MagicMock, patch

    mock_provider = MagicMock()
    with patch("pr_agent.tools.pr_code_agent.get_git_provider_with_context", return_value=mock_provider):
        agent = PRCodeAgent(pr_url="https://github.com/org/repo/pull/1")

        registered_tools = agent.registry.tools.keys()

        expected_tools = [
            "list_files",
            "read_file",
            "edit_file",
            "delete_file",
            "rename_file",
            "replace_with_git_merge_diff",
            "view_image",
            "view_text_website",
            "run_in_bash_session",
            "set_plan",
            "plan_step_complete",
            "request_plan_review",
            "request_code_review",
            "finish"
        ]

        for tool in expected_tools:
            assert tool in registered_tools, f"Tool '{tool}' is missing from PRCodeAgent registry"

def test_jules_code_standards_enforcement_strict():
    """
    Strictly verify that the core files implementing the 'Jules' agent are under 150 lines.
    This test serves as a gatekeeper for the strict size limit.
    """
    files_to_check = [
        "pr_agent/tools/pr_code_agent.py",
        "pr_agent/tools/code_agent/tools.py",
        "pr_agent/tools/code_agent/prompts.py",
        "pr_agent/tools/code_agent/utils.py",
        "pr_agent/tools/code_agent/tool_registry.py",
        "pr_agent/tools/code_agent/diff_utils.py"
    ]

    MAX_LINES = 150

    for filepath in files_to_check:
        assert os.path.exists(filepath), f"File {filepath} does not exist"
        with open(filepath, 'r') as f:
            line_count = sum(1 for _ in f)

        assert line_count < MAX_LINES, f"File {filepath} has {line_count} lines, exceeding the strict limit of {MAX_LINES}"
