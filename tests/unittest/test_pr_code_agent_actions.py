import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pr_agent.tools.pr_code_agent import PRCodeAgent
from pr_agent.tools.code_agent.tools import AgentTools

@pytest.mark.asyncio
async def test_pr_code_agent_delete_file():
    # Mock dependencies
    mock_provider = MagicMock()
    mock_provider.get_files.return_value = [MagicMock(filename="to_delete.py")]
    mock_provider.get_pr_file_content.return_value = "Content"
    mock_provider.get_pr_branch.return_value = "feature-branch"

    # Mock delete_file specifically to avoid side effects (though it's mocked)
    mock_provider.delete_file = MagicMock()

    mock_ai_handler = MagicMock()
    # Simulate: List Files -> Delete File -> Finish
    mock_ai_handler.chat_completion = AsyncMock(side_effect=[
        ['```json\n{"action": "list_files", "args": {"path": "."}}\n```'],
        ['```json\n{"action": "delete_file", "args": {"file_path": "to_delete.py"}}\n```'],
        ['```json\n{"action": "finish", "args": {"message": "Done"}}\n```']
    ])

    with patch('pr_agent.tools.pr_code_agent.get_git_provider_with_context', return_value=mock_provider):
        with patch('subprocess.run', side_effect=Exception("No shell")), \
             patch('builtins.open', new_callable=MagicMock), \
             patch('os.remove', new_callable=MagicMock) as mock_os_remove, \
             patch('os.path.exists', return_value=True): # For local delete check

             agent = PRCodeAgent("https://github.com/org/repo/pull/1", args=["Delete file"], ai_handler=lambda: mock_ai_handler)
             await agent.run()

    # Assertions
    mock_provider.delete_file.assert_called_with("to_delete.py", "feature-branch", "Agent deleted file")
    mock_os_remove.assert_called_with("to_delete.py")
    mock_provider.publish_comment.assert_called_with("Task Done: Done")


@pytest.mark.asyncio
async def test_pr_code_agent_rename_file():
    # Mock dependencies
    mock_provider = MagicMock()
    mock_provider.get_files.return_value = [MagicMock(filename="old.py")]
    mock_provider.get_pr_file_content.return_value = "Content of old file"
    mock_provider.get_pr_branch.return_value = "feature-branch"

    mock_provider.create_or_update_pr_file = MagicMock()
    mock_provider.delete_file = MagicMock()

    mock_ai_handler = MagicMock()
    # Simulate: Rename File -> Finish
    mock_ai_handler.chat_completion = AsyncMock(side_effect=[
        ['```json\n{"action": "rename_file", "args": {"filepath": "old.py", "new_filepath": "new.py"}}\n```'],
        ['```json\n{"action": "finish", "args": {"message": "Done"}}\n```']
    ])

    with patch('pr_agent.tools.pr_code_agent.get_git_provider_with_context', return_value=mock_provider):
        with patch('subprocess.run', side_effect=Exception("No shell")), \
             patch('builtins.open', new_callable=MagicMock), \
             patch('os.remove', new_callable=MagicMock), \
             patch('os.path.exists', return_value=True), \
             patch('os.makedirs'):

             agent = PRCodeAgent("https://github.com/org/repo/pull/1", args=["Rename file"], ai_handler=lambda: mock_ai_handler)
             await agent.run()

    # Assertions
    # Rename involves: Read -> Edit (Create new) -> Delete old
    mock_provider.get_pr_file_content.assert_called_with("old.py", "feature-branch")
    mock_provider.create_or_update_pr_file.assert_called_with("new.py", "feature-branch", "Content of old file", "Agent edit")
    mock_provider.delete_file.assert_called_with("old.py", "feature-branch", "Agent deleted file")
    mock_provider.publish_comment.assert_called_with("Task Done: Done")


@pytest.mark.asyncio
async def test_pr_code_agent_enforce_limit():
    # Mock dependencies
    mock_provider = MagicMock()
    mock_provider.get_files.return_value = []
    mock_provider.get_pr_branch.return_value = "feature-branch"

    mock_ai_handler = MagicMock()
    # Simulate:
    # 1. Agent tries to create a large file (> 150 lines).
    # 2. Tool returns warning.
    # 3. Agent refactors (splits into smaller files).
    # 4. Finish.

    import json
    large_content = "\n".join(["code"] * 160)
    small_content_1 = "\n".join(["code"] * 80)
    small_content_2 = "\n".join(["code"] * 80)

    def make_response(action, args):
        return [f'```json\n{json.dumps({"action": action, "args": args})}\n```']

    mock_ai_handler.chat_completion = AsyncMock(side_effect=[
        make_response("edit_file", {"file_path": "large.py", "content": large_content}),
        # Agent sees warning in history (implicitly handled by PRCodeAgent loop adding result to history)
        # Agent decides to split
        make_response("edit_file", {"file_path": "part1.py", "content": small_content_1}),
        make_response("edit_file", {"file_path": "part2.py", "content": small_content_2}),
        make_response("delete_file", {"file_path": "large.py"}), # Cleanup large file if created
        make_response("finish", {"message": "Refactored"})
    ])

    with patch('pr_agent.tools.pr_code_agent.get_git_provider_with_context', return_value=mock_provider):
        with patch('subprocess.run', side_effect=Exception("No shell")), \
             patch('builtins.open', new_callable=MagicMock), \
             patch('os.remove', new_callable=MagicMock), \
             patch('os.path.exists', return_value=False), \
             patch('os.makedirs'):

             agent = PRCodeAgent("https://github.com/org/repo/pull/1", args=["Create large file"], ai_handler=lambda: mock_ai_handler)
             await agent.run()

    # Assertions
    # Verify large file creation was attempted (and warned)
    # Verify smaller files were created
    assert mock_provider.create_or_update_pr_file.call_count >= 3
    calls = mock_provider.create_or_update_pr_file.call_args_list

    # Check for large content attempt
    found_large = False
    for call in calls:
        if call.args[0] == "large.py" and call.args[2] == large_content:
            found_large = True
            break
    assert found_large, "Did not find call creating large.py with large content"

    # Check for split content
    found_part1 = False
    found_part2 = False
    for call in calls:
        if call.args[0] == "part1.py" and call.args[2] == small_content_1:
            found_part1 = True
        if call.args[0] == "part2.py" and call.args[2] == small_content_2:
            found_part2 = True

    assert found_part1, "Did not find call creating part1.py"
    assert found_part2, "Did not find call creating part2.py"

    # Check for delete of large file
    mock_provider.delete_file.assert_called_with("large.py", "feature-branch", "Agent deleted file")
