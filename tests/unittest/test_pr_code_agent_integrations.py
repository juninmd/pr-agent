import pytest
from unittest.mock import MagicMock, patch
from pr_agent.tools.pr_code_agent import PRCodeAgent

class TestPRCodeAgentIntegrations:
    @patch("pr_agent.tools.pr_code_agent.LiteLLMAIHandler")
    @patch("pr_agent.git_providers.get_settings")
    @patch("pr_agent.tools.pr_code_agent.get_settings")
    def test_github_integration(self, mock_settings_agent, mock_settings_gp, mock_ai_handler):
        """
        Verify that PRCodeAgent correctly integrates with GitHubProvider
        when configured for GitHub.
        """
        # Setup configuration
        mock_settings_gp.return_value.config.git_provider = "github"
        mock_settings_agent.return_value.config.git_provider = "github"

        # Create a mock for the provider class
        MockGithubProvider = MagicMock()

        # Patch the _GIT_PROVIDERS dictionary to use our mock
        with patch.dict("pr_agent.git_providers._GIT_PROVIDERS", {"github": MockGithubProvider}):
            # Instantiate agent, passing the mock AI handler explicitly to avoid import/definition time issues
            agent = PRCodeAgent(pr_url="https://github.com/org/repo/pull/1", ai_handler=mock_ai_handler)

            # Assertions
            # The agent calls the class (our mock) to instantiate the provider
            MockGithubProvider.assert_called_once()
            # The agent's provider attribute should be the return value of the class call
            assert agent.git_provider == MockGithubProvider.return_value
            # The agent's ai_handler should be the return value of the mocked class we passed
            assert agent.ai_handler == mock_ai_handler.return_value

    @patch("pr_agent.tools.pr_code_agent.LiteLLMAIHandler")
    @patch("pr_agent.git_providers.get_settings")
    @patch("pr_agent.tools.pr_code_agent.get_settings")
    def test_gitlab_integration(self, mock_settings_agent, mock_settings_gp, mock_ai_handler):
        """
        Verify that PRCodeAgent correctly integrates with GitLabProvider
        when configured for GitLab.
        """
        # Setup configuration
        mock_settings_gp.return_value.config.git_provider = "gitlab"
        mock_settings_agent.return_value.config.git_provider = "gitlab"

        # Create a mock for the provider class
        MockGitLabProvider = MagicMock()

        # Patch the _GIT_PROVIDERS dictionary to use our mock
        with patch.dict("pr_agent.git_providers._GIT_PROVIDERS", {"gitlab": MockGitLabProvider}):
            # Instantiate agent
            agent = PRCodeAgent(pr_url="https://gitlab.com/org/repo/-/merge_requests/1", ai_handler=mock_ai_handler)

            # Assertions
            MockGitLabProvider.assert_called_once()
            assert agent.git_provider == MockGitLabProvider.return_value
            assert agent.ai_handler == mock_ai_handler.return_value
