import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pr_agent.tools.pr_code_agent import PRCodeAgent

@pytest.mark.asyncio
async def test_pr_code_agent_delete_file_flow():
    # Mock dependencies
    mock_provider = MagicMock()
    mock_provider.get_files.return_value = [MagicMock(filename="deleteme.txt")]
    mock_provider.get_pr_file_content.return_value = "Content to delete"
    mock_provider.get_pr_branch.return_value = "feature-branch"

    mock_ai_handler = MagicMock()
    # Simulate: List Files -> Delete File -> Finish
    mock_ai_handler.chat_completion = AsyncMock(side_effect=[
        ['```json\n{"action": "list_files", "args": {"path": "."}}\n```'],
        ['```json\n{"action": "delete_file", "args": {"file_path": "deleteme.txt"}}\n```'],
        ['```json\n{"action": "finish", "args": {"message": "Deleted"}}\n```']
    ])

    with patch('pr_agent.tools.pr_code_agent.get_git_provider_with_context', return_value=mock_provider):
        # We need to mock subprocess for list_files to avoid actual shell call
        # We also mock os.path.exists and os.remove to prevent local file operations
        with patch('subprocess.run', side_effect=Exception("No shell")), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove') as mock_remove:

             agent = PRCodeAgent("https://github.com/org/repo/pull/1", args=["Delete file"], ai_handler=lambda: mock_ai_handler)
             await agent.run()

    # Assertions
    assert mock_ai_handler.chat_completion.call_count == 3
    # Verify provider delete_file was called
    mock_provider.delete_file.assert_called_with("deleteme.txt", "feature-branch", "Agent deleted file")
    # Verify local remove was called
    mock_remove.assert_called_with("deleteme.txt")

    mock_provider.publish_comment.assert_called_with("Task Done: Deleted")
