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
