import pytest
from unittest.mock import patch, MagicMock

def test_github_provider_import_and_init():
    """
    Test that GithubProvider can be imported and initialized.
    This verifies that all dependencies (like tenacity) are installed correctly in the CI environment.
    """
    try:
        from pr_agent.git_providers.github_provider import GithubProvider
    except ImportError as e:
        pytest.fail(f"Failed to import GithubProvider: {e}")

    # Mock settings to allow initialization without actual config files
    with patch("pr_agent.git_providers.github_provider.get_settings") as mock_settings, \
         patch("pr_agent.git_providers.github_provider.Github") as mock_github_client:

        # Setup mock settings structure
        mock_settings.return_value.get.side_effect = lambda key, default=None: {
            "GITHUB.BASE_URL": "https://api.github.com",
            "GITHUB.DEPLOYMENT_TYPE": "user"
        }.get(key, default)

        mock_settings.return_value.github.user_token = "fake_token"
        mock_settings.return_value.github.ratelimit_retries = 5

        # Initialize provider
        try:
            provider = GithubProvider()
            assert provider
        except Exception as e:
            pytest.fail(f"Failed to initialize GithubProvider: {e}")
