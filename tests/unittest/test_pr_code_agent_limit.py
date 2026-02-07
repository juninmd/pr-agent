import pytest
from unittest.mock import MagicMock, patch
from pr_agent.tools.code_agent.tools import AgentTools

@pytest.mark.asyncio
async def test_edit_file_warning_limit():
    mock_provider = MagicMock()
    # Mock os.path.exists to avoid actual file system ops errors or logic
    with patch("os.path.exists", return_value=False):
        tools = AgentTools(mock_provider)

        # Test file > 150 lines
        content = "\n".join(["line"] * 151)
        res = await tools.edit_file("test.py", content)

        assert "WARNING: File has 151 lines, exceeding the strict 150-line limit" in res
        mock_provider.create_or_update_pr_file.assert_called_once()

@pytest.mark.asyncio
async def test_edit_file_no_warning():
    mock_provider = MagicMock()
    with patch("os.path.exists", return_value=False):
        tools = AgentTools(mock_provider)

        # Test file <= 150 lines
        content = "\n".join(["line"] * 150)
        res = await tools.edit_file("test.py", content)

        assert "WARNING" not in res
