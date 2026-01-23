import unittest
from unittest.mock import MagicMock, patch
from pr_agent.git_providers.gitlab_provider import GitLabProvider
from pr_agent.tools.code_agent.tools import AgentTools
from pr_agent.config_loader import get_settings

class TestGitLabTokenEconomy(unittest.TestCase):
    def setUp(self):
        self.mock_settings = MagicMock()
        self.mock_settings.config.token_economy_mode = True
        self.mock_settings.get.return_value = True # for get("token_economy_mode", False)

    @patch("pr_agent.git_providers.gitlab_provider.get_settings")
    @patch("pr_agent.git_providers.gitlab_provider.gitlab.Gitlab")
    def test_gitlab_provider_init_token_economy(self, mock_gitlab, mock_get_settings):
        # Setup settings for this test
        mock_get_settings.return_value.config.get.return_value = True # token_economy_mode
        mock_get_settings.return_value.get.side_effect = lambda k, d=None: {
            "GITLAB.URL": "https://gitlab.com",
            "GITLAB.PERSONAL_ACCESS_TOKEN": "token",
            "GITLAB.AUTH_TYPE": "oauth_token",
            "config.token_economy_mode": True
        }.get(k, d)

        # Initialize provider
        provider = GitLabProvider(merge_request_url="https://gitlab.com/owner/repo/merge_requests/1")

        # Verify settings were updated
        # The provider calls get_settings().set("config.patch_extra_lines_before", 0)
        mock_get_settings.return_value.set.assert_any_call("config.patch_extra_lines_before", 0)
        mock_get_settings.return_value.set.assert_any_call("config.patch_extra_lines_after", 0)

    @patch("pr_agent.tools.code_agent.tools.get_settings")
    def test_agent_tools_read_file_truncation(self, mock_get_settings):
        # Setup settings
        mock_get_settings.return_value.config.token_economy_mode = True

        # Mock provider
        mock_provider = MagicMock()
        large_content = "line\n" * 10000 # 10000 lines
        mock_provider.get_pr_file_content.return_value = large_content
        mock_provider.get_pr_branch.return_value = "main"

        # Initialize tools
        tools = AgentTools(mock_provider)

        # Call read_file
        import asyncio
        content = asyncio.run(tools.read_file("some_file.py"))

        # Assert content is truncated
        # We expect it to be significantly smaller than the original
        self.assertTrue(len(content) < len(large_content))
        self.assertIn("truncated", content.lower())
