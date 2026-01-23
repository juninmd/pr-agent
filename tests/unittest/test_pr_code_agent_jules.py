import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pr_agent.tools.pr_code_agent import PRCodeAgent

@pytest.mark.asyncio
async def test_pr_code_agent_jules_persona_flow():
    # Mock dependencies
    mock_provider = MagicMock()
    mock_provider.get_files.return_value = [MagicMock(filename="README.md")]
    mock_provider.get_pr_file_content.return_value = "Original content"
    mock_provider.get_pr_branch.return_value = "feature-branch"

    mock_ai_handler = MagicMock()
    # Simulate: List Files -> Plan -> Read -> Edit -> Read (Verify) -> Finish
    # This matches the "Jules" workflow (Plan, Act, Verify)
    mock_ai_handler.chat_completion = AsyncMock(side_effect=[
        ['```json\n{"action": "list_files", "args": {"path": "."}}\n```'],
        ['```json\n{"action": "set_plan", "args": {"plan": ["Read README", "Update README", "Verify", "Finish"]}}\n```'],
        ['```json\n{"action": "read_file", "args": {"file_path": "README.md"}}\n```'],
        ['```json\n{"action": "edit_file", "args": {"file_path": "README.md", "content": "New content"}}\n```'],
        ['```json\n{"action": "read_file", "args": {"file_path": "README.md"}}\n```'],
        ['```json\n{"action": "finish", "args": {"message": "Done"}}\n```']
    ])

    with patch('pr_agent.tools.pr_code_agent.get_git_provider_with_context', return_value=mock_provider):
        # We need to mock subprocess for list_files to avoid actual shell call, or let it fail and fallback
        # We also mock open to prevent overwriting local files during test
        with patch('subprocess.run', side_effect=Exception("No shell")), \
             patch('builtins.open', new_callable=MagicMock):
             agent = PRCodeAgent("https://github.com/org/repo/pull/1", args=["Improve README"], ai_handler=lambda: mock_ai_handler)
             await agent.run()

    # Assertions
    assert mock_ai_handler.chat_completion.call_count == 6
    mock_provider.create_or_update_pr_file.assert_called_with("README.md", "feature-branch", "New content", "Agent edit")
    mock_provider.publish_comment.assert_called_with("Task Done: Done")

    # Verify tool definitions include args
    tool_defs = agent.registry.get_tool_definitions()
    assert "list_files(path: str = '.')" in tool_defs
    assert "edit_file(file_path: str, content: str)" in tool_defs
