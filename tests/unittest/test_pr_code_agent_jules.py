import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pr_agent.tools.pr_code_agent import PRCodeAgent

@pytest.mark.asyncio
async def test_pr_code_agent_flow():
    # Mock dependencies
    mock_provider = MagicMock()
    mock_provider.get_files.return_value = [MagicMock(filename="README.md")]
    mock_provider.get_pr_file_content.return_value = "Original content"
    mock_provider.get_pr_branch.return_value = "feature-branch"

    mock_ai_handler = MagicMock()
    # Simulate a sequence of responses: Plan -> Read -> Finish
    mock_ai_handler.chat_completion = AsyncMock(side_effect=[
        ['```json\n{"action": "set_plan", "args": {"plan": ["Read file", "Finish"]}}\n```'],
        ['```json\n{"action": "read_file", "args": {"file_path": "README.md"}}\n```'],
        ['```json\n{"action": "finish", "args": {"message": "Done"}}\n```']
    ])

    with patch('pr_agent.tools.pr_code_agent.get_git_provider_with_context', return_value=mock_provider):
        agent = PRCodeAgent("https://github.com/org/repo/pull/1", args=["fix bug"], ai_handler=lambda: mock_ai_handler)
        await agent.run()

    # Assertions
    assert mock_ai_handler.chat_completion.call_count == 3
    # Check if tools were called via registry/tools logic
    # We can inspect the history or mock_provider calls
    mock_provider.get_pr_file_content.assert_called_with("README.md", "feature-branch")
    mock_provider.publish_comment.assert_called_with("Task Done: Done")

@pytest.mark.asyncio
async def test_pr_code_agent_list_files_fallback():
    mock_provider = MagicMock()
    mock_provider.get_files.return_value = [MagicMock(filename="fallback.txt")]

    with patch('pr_agent.tools.pr_code_agent.get_git_provider_with_context', return_value=mock_provider):
        agent = PRCodeAgent("url")
        # Direct tool call test, force subproccess failure to test fallback
        with patch('subprocess.run', side_effect=Exception("Fail")):
            files = await agent.tools.list_files()
            assert "fallback.txt" in files
