import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pr_agent.tools.code_agent.tools import AgentTools

@pytest.mark.asyncio
async def test_agent_tools_rename():
    mock_provider = MagicMock()
    mock_provider.get_pr_file_content.return_value = "content"
    mock_provider.get_pr_branch.return_value = "branch"

    tools = AgentTools(mock_provider)

    with patch("builtins.open", new_callable=MagicMock), \
         patch("os.path.exists", return_value=True), \
         patch("os.remove") as mock_remove:

        res = await tools.rename_file("old.txt", "new.txt")

        assert res == "Renamed old.txt to new.txt"
        mock_provider.get_pr_file_content.assert_called_with("old.txt", "branch")
        mock_provider.create_or_update_pr_file.assert_called_with("new.txt", "branch", "content", "Agent edit")
        mock_provider.delete_file.assert_called_with("old.txt", "branch", "Agent deleted file")
        # Local delete should also happen
        mock_remove.assert_called_with("old.txt")

@pytest.mark.asyncio
async def test_agent_tools_diff():
    mock_provider = MagicMock()
    original_content = "line1\nline2\nline3"
    mock_provider.get_pr_file_content.return_value = original_content
    mock_provider.get_pr_branch.return_value = "branch"

    tools = AgentTools(mock_provider)

    merge_diff = """<<<<<<< SEARCH
line2
=======
line2_modified
>>>>>>> REPLACE"""

    with patch("builtins.open", new_callable=MagicMock), \
         patch("os.path.exists", return_value=True):

        res = await tools.replace_with_git_merge_diff("file.txt", merge_diff)

        assert res == "Applied diff to file.txt"
        expected_content = "line1\nline2_modified\nline3"
        mock_provider.create_or_update_pr_file.assert_called_with("file.txt", "branch", expected_content, "Agent edit")

@pytest.mark.asyncio
async def test_agent_tools_other():
    mock_provider = MagicMock()
    tools = AgentTools(mock_provider)

    res = await tools.view_image("http://example.com/img.png")
    assert res == "Image viewed: http://example.com/img.png"

    res = await tools.request_plan_review("My Plan")
    assert "Plan review requested" in res

    res = await tools.request_code_review()
    assert "Code review requested" in res
