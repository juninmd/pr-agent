import pytest
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Mock logging and missing dependencies first
if "litellm" not in sys.modules:
    sys.modules["litellm"] = MagicMock()
if "openai" not in sys.modules:
    sys.modules["openai"] = MagicMock()
if "pr_agent.log" not in sys.modules:
    sys.modules["pr_agent.log"] = MagicMock()
if "loguru" not in sys.modules:
    sys.modules["loguru"] = MagicMock()

# Mock config_loader to avoid heavy dependencies like starlette
if "pr_agent.config_loader" not in sys.modules:
    config_mock = MagicMock()
    config_mock.get_settings.return_value.config.model = "gpt-4"
    config_mock.get_settings.return_value.github.user_token = "dummy_token"
    # Mock AWS keys as strings to avoid TypeError in os.environ assignment
    config_mock.get_settings.return_value.aws.AWS_ACCESS_KEY_ID = "test_key"
    config_mock.get_settings.return_value.aws.AWS_SECRET_ACCESS_KEY = "test_secret"
    config_mock.get_settings.return_value.aws.AWS_SESSION_TOKEN = "test_token"
    config_mock.get_settings.return_value.aws.AWS_REGION = "us-east-1"
    config_mock.get_settings.return_value.aws.AWS_REGION_NAME = "us-east-1"
    config_mock.get_settings.return_value.google_ai_studio.gemini_api_key = "dummy_key"
    config_mock.get_settings.return_value.vertexai.location = "us-central1"
    config_mock.get_settings.return_value.vertexai.project = "dummy_project"
    config_mock.get_settings.return_value.get.return_value = "dummy_value"
    sys.modules["pr_agent.config_loader"] = config_mock

if "starlette_context" not in sys.modules:
    sys.modules["starlette_context"] = MagicMock()
if "azure" not in sys.modules:
    sys.modules["azure"] = MagicMock()
if "azure.identity" not in sys.modules:
    sys.modules["azure.identity"] = MagicMock()

# Now import modules under test
from pr_agent.jules.agent import JulesAgent
from pr_agent.jules.planner import Planner, Plan, Step
from pr_agent.jules.state import State
from pr_agent.jules.tools import JulesTools

@pytest.mark.asyncio
async def test_planner_create_plan():
    """Test planner plan generation."""
    planner = Planner()
    planner.ai.chat_completion = AsyncMock(return_value=(
        '{"steps": [{"description": "test step", "command": "echo 1"}]}',
        "stop"
    ))

    plan = await planner.create_plan("do something", "file1.py")
    assert len(plan.steps) == 1
    assert plan.steps[0].description == "test step"

@pytest.mark.asyncio
async def test_agent_run_loop():
    """Test the full agent loop."""
    # Mock Git Provider
    mock_git = MagicMock()
    mock_git.get_current_branch.return_value = "main"

    # Mock Agent
    agent = JulesAgent(mock_git)
    agent.tools.list_files = AsyncMock(return_value="file1.py\nfile2.py")

    # Mock Planner
    agent.planner.create_plan = AsyncMock(return_value=Plan(
        steps=[Step(description="edit file", command="edit_file file1.py content")],
        goal="edit file"
    ))
    # Mock the tool calling prompt response
    agent.planner.ai.chat_completion = AsyncMock(return_value=(
        '{"tool": "read_file", "args": {"file_path": "file1.py"}}',
        "stop"
    ))

    # Mock Tool Execution directly on the tools instance
    agent.tools.read_file = AsyncMock(return_value="content of file1")

    res = await agent.run("test task")
    assert res == "Task Completed"

def test_clean_code_constraints():
    """Verify files are under 150 lines of code."""
    files_to_check = [
        "pr_agent/jules/agent.py",
        "pr_agent/jules/planner.py",
        "pr_agent/jules/state.py",
        "pr_agent/jules/tools.py",
        "pr_agent/jules/git/provider.py",
        "pr_agent/jules/git/github/files.py",
        "pr_agent/jules/git/gitlab/files.py"
    ]

    for fpath in files_to_check:
        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                lines = f.readlines()
                # Simple LOC count: non-empty lines
                loc = len([l for l in lines if l.strip()])
                assert loc < 150, f"{fpath} has {loc} LOC, exceeding limit of 150."
