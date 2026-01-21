from unittest.mock import MagicMock, patch, call
import pytest
from pr_agent.git_providers.gitlab_provider import GitLabProvider
from pr_agent.algo.utils import get_max_tokens

class TestGitLabGeminiConfig:
    @pytest.fixture
    def mock_gitlab_client(self):
        client = MagicMock()
        return client

    @pytest.fixture
    def mock_project(self):
        project = MagicMock()
        return project

    @pytest.fixture
    def mock_settings(self):
        with patch('pr_agent.git_providers.gitlab_provider.get_settings') as mock_settings:
            # Setup default settings for the test
            settings_dict = {
                "GITLAB.URL": "https://gitlab.com",
                "GITLAB.PERSONAL_ACCESS_TOKEN": "fake_token",
                "CONFIG.TOKEN_ECONOMY_MODE": True,
                "CONFIG.MODEL": "gemini/gemini-1.5-flash",
                "CONFIG.MAX_MODEL_TOKENS": 32000,
            }

            # Configure the config object behavior for property access
            mock_config = MagicMock()
            mock_config.get.side_effect = lambda key, default=None: {
                "token_economy_mode": True,
                "max_files_in_economy_mode": 6,
            }.get(key, default)
            mock_config.token_economy_mode = True
            mock_config.max_model_tokens = 32000
            mock_config.custom_model_max_tokens = -1

            # Link .config property to our configured mock
            mock_settings.return_value.config = mock_config

            # Configure main get method
            mock_settings.return_value.get.side_effect = lambda key, default=None: settings_dict.get(key, default)

            yield mock_settings

    @pytest.fixture
    def gitlab_provider(self, mock_gitlab_client, mock_project, mock_settings):
        with patch('pr_agent.git_providers.gitlab_provider.gitlab.Gitlab', return_value=mock_gitlab_client):
            mock_gitlab_client.projects.get.return_value = mock_project
            provider = GitLabProvider("https://gitlab.com/test/repo/-/merge_requests/1")
            provider.gl = mock_gitlab_client
            provider.id_project = "test/repo"
            # Setup MR mock
            mock_mr = MagicMock()
            mock_mr.changes.return_value = {'changes': []}
            mock_mr.diffs.list.return_value = []
            provider.mr = mock_mr
            return provider

    def test_gitlab_token_economy_file_limit(self, gitlab_provider, mock_settings):
        """Test that token economy mode limits the number of files processed."""
        # Setup many changes
        changes = []
        for i in range(20):
            changes.append({
                'new_path': f'file_{i}.py',
                'old_path': f'file_{i}.py',
                'diff': 'some diff',
                'new_file': False,
                'deleted_file': False,
                'renamed_file': False
            })

        gitlab_provider.mr.changes.return_value = {'changes': changes}

        # Mock get_pr_file_content to avoid actual calls
        gitlab_provider.get_pr_file_content = MagicMock(return_value="content")

        diff_files = gitlab_provider.get_diff_files()

        # In token_economy_mode=True, max_files_allowed is 6 (hardcoded currently)
        # Verify that we got all files in the list, but content loading might differ
        assert len(diff_files) == 20

        # Check how many times we loaded full content.
        # The logic calls get_pr_file_content twice (old/new) for the first 6 files.
        assert gitlab_provider.get_pr_file_content.call_count == 12

    def test_gitlab_economy_context_reduction(self, mock_gitlab_client, mock_project, mock_settings):
        """Test that initializing GitLabProvider in economy mode reduces patch extra lines."""
        with patch('pr_agent.git_providers.gitlab_provider.gitlab.Gitlab', return_value=mock_gitlab_client):
            GitLabProvider("https://gitlab.com/test/repo/-/merge_requests/1")

            # Verify that settings were updated
            mock_settings.return_value.set.assert_has_calls([
                call("config.patch_extra_lines_before", 0),
                call("config.patch_extra_lines_after", 0)
            ], any_order=True)

    def test_gemini_max_tokens(self, mock_settings):
        """Test that get_max_tokens returns the capped value for Gemini."""
        with patch('pr_agent.algo.utils.get_settings', mock_settings):
            max_tokens = get_max_tokens("gemini/gemini-1.5-flash")
            # Should be capped at 32000 by config.max_model_tokens
            assert max_tokens == 32000
