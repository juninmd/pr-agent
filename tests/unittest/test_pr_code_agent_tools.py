import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pr_agent.tools.code_agent.tools import AgentTools

@pytest.mark.asyncio
async def test_view_text_website():
    # Mock GitProvider
    mock_provider = MagicMock()
    tools = AgentTools(mock_provider)

    # Mock aiohttp response object
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text.return_value = "<html><body><h1>Title</h1><p>Content</p></body></html>"

    # Mock the return value of session.get() -> returns a context manager
    mock_get_ctx = MagicMock()
    mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_get_ctx.__aexit__ = AsyncMock(return_value=None)

    # Mock the session object
    mock_session = MagicMock()
    mock_session.get.return_value = mock_get_ctx

    # Mock the return value of ClientSession() -> returns a context manager
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

    # Mock ClientSession class
    with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
        # Call the tool
        result = await tools.view_text_website("http://example.com")

    # Assertions
    # html2text converts <h1>Title</h1> to "# Title\n\n" and <p>Content</p> to "Content\n\n"
    assert "Title" in result
    assert "Content" in result
    assert "Error" not in result

@pytest.mark.asyncio
async def test_view_text_website_error():
    # Mock GitProvider
    mock_provider = MagicMock()
    tools = AgentTools(mock_provider)

    # Mock aiohttp response error
    mock_response = AsyncMock()
    mock_response.status = 404

    mock_get_ctx = MagicMock()
    mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_get_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get.return_value = mock_get_ctx

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
        result = await tools.view_text_website("http://example.com")

    assert "Error" in result
    assert "404" in result

@pytest.mark.asyncio
async def test_view_text_website_invalid_url():
    mock_provider = MagicMock()
    tools = AgentTools(mock_provider)
    result = await tools.view_text_website("ftp://example.com")
    assert "Error: URL must start with" in result

@pytest.mark.asyncio
async def test_list_files_gitlab_string_fix():
    """Test that list_files handles GitProvider returning strings (GitLab behavior)."""
    # Mock GitProvider to simulate GitLab behavior (get_files returns strings)
    mock_provider = MagicMock()
    mock_provider.get_files.return_value = ["file1.py", "file2.py"]

    tools = AgentTools(mock_provider)

    # Force fallback to git_provider by mocking subprocess.run to fail
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1 # Simulate failure

        result = await tools.list_files()
        assert "file1.py" in result
        assert "file2.py" in result

@pytest.mark.asyncio
async def test_list_files_github_object_fix():
    """Test that list_files handles GitProvider returning objects (GitHub behavior)."""
    # Mock GitProvider to simulate GitHub behavior (get_files returns objects)
    mock_provider = MagicMock()
    mock_file1 = MagicMock()
    mock_file1.filename = "file1.py"
    mock_file2 = MagicMock()
    mock_file2.filename = "file2.py"
    mock_provider.get_files.return_value = [mock_file1, mock_file2]

    tools = AgentTools(mock_provider)

    # Force fallback to git_provider by mocking subprocess.run to fail
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1 # Simulate failure

        result = await tools.list_files()
        assert "file1.py" in result
        assert "file2.py" in result
