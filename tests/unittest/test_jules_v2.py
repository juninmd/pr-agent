import sys
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from pr_agent.jules.planner import Planner, Step, Plan
from pr_agent.jules.tools import JulesTools
from pr_agent.jules.agent import JulesAgent
from pr_agent.jules.git.provider import GitProvider

class MockGitProvider(GitProvider):
    def get_pr_url(self): return "http://mock"
    def get_current_branch(self): return "main"
    def get_files(self): return ["a.py"]
    def get_file_content(self, path, branch=None): return "content"
    def create_or_update_file(self, path, content, msg, branch): pass
    def delete_file(self, path, msg, branch): pass
    def create_pr(self, title, body, src, tgt): return "url"
    def add_comment(self, body): pass

@pytest.fixture
def mock_settings():
    with patch("pr_agent.config_loader.get_settings") as mock_get:
        mock_get.return_value.config.model = "gpt-4"
        yield mock_get

@pytest.mark.asyncio
async def test_planner_create_plan(mock_settings):
    with patch("pr_agent.jules.planner.LiteLLMAIHandler") as MockAI:
        mock_ai_instance = MockAI.return_value
        mock_ai_instance.chat_completion = AsyncMock(return_value=(
            '{"steps": [{"description": "step1", "command": "cmd1"}]}', "stop"
        ))

        # We need to patch get_settings in planner module specifically if it imported it
        # But usually config_loader.get_settings is sufficient if imported from there
        with patch("pr_agent.jules.planner.get_settings", new=mock_settings):
             planner = Planner()
             plan = await planner.create_plan("task", "file context")

             assert len(plan.steps) == 1
             assert plan.steps[0].description == "step1"
             assert plan.steps[0].command == "cmd1"

@pytest.mark.asyncio
async def test_tools_edit_file():
    mock_git = MockGitProvider()
    mock_git.create_or_update_file = MagicMock()
    mock_git.get_current_branch = MagicMock(return_value="main")

    tools = JulesTools(mock_git)
    # Patch os.makedirs and open to avoid real file IO
    with patch("os.makedirs"), patch("builtins.open", new_callable=MagicMock):
        res = await tools.edit_file("path/to/file.py", "new content")

        assert "Successfully edited" in res
        mock_git.create_or_update_file.assert_called_once()

@pytest.mark.asyncio
async def test_agent_run(mock_settings):
    mock_git = MockGitProvider()

    # Mock Planner to return a fixed plan
    with patch("pr_agent.jules.agent.Planner") as MockPlanner:
        mock_planner_instance = MockPlanner.return_value
        mock_planner_instance.create_plan = AsyncMock(return_value=Plan(
            steps=[Step("do something", "cmd")], goal="goal"
        ))

        # Mock AI in Agent to return a tool call
        with patch("pr_agent.jules.agent.LiteLLMAIHandler") as MockAI:
            mock_ai_instance = MockAI.return_value
            mock_ai_instance.chat_completion = AsyncMock(return_value=(
                '{"tool": "run_command", "args": {"command": "echo hello"}}', "stop"
            ))

            with patch("pr_agent.jules.agent.get_settings", new=mock_settings):
                agent = JulesAgent(mock_git)

                # Patch tools.run_command and list_files
                with patch.object(agent.tools, 'run_command', new_callable=AsyncMock) as mock_run_cmd:
                    mock_run_cmd.return_value = "hello"
                    with patch.object(agent.tools, 'list_files', new_callable=AsyncMock) as mock_list:
                        mock_list.return_value = "file list"

                        await agent.run("my task")

                        mock_planner_instance.create_plan.assert_called_once()
                        mock_ai_instance.chat_completion.assert_called()
                        mock_run_cmd.assert_called_with(command="echo hello")
