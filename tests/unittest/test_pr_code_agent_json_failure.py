import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pr_agent.tools.pr_code_agent import PRCodeAgent

@pytest.mark.asyncio
async def test_pr_code_agent_json_recovery():
    # Mock dependencies
    mock_provider = MagicMock()
    mock_provider.get_files.return_value = [MagicMock(filename="README.md")]
    mock_provider.get_pr_file_content.return_value = "Original content"
    mock_provider.get_pr_branch.return_value = "feature-branch"

    mock_ai_handler = MagicMock()
    # Simulate: Invalid JSON -> Finish
    mock_ai_handler.chat_completion = AsyncMock(side_effect=[
        ['Invalid JSON response'],
        ['```json\n{"action": "finish", "args": {"message": "Recovered"}}\n```']
    ])

    with patch('pr_agent.tools.pr_code_agent.get_git_provider_with_context', return_value=mock_provider):
        with patch('subprocess.run', side_effect=Exception("No shell")),              patch('builtins.open', new_callable=MagicMock):
             agent = PRCodeAgent("https://github.com/org/repo/pull/1", args=["Task"], ai_handler=lambda: mock_ai_handler)
             await agent.run()

    # Assertions
    assert mock_ai_handler.chat_completion.call_count == 2
    mock_provider.publish_comment.assert_called_with("Task Done: Recovered")
