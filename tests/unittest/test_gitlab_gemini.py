from unittest.mock import MagicMock, patch
import pytest
from gitlab import Gitlab
from pr_agent.git_providers.gitlab_provider import GitLabProvider
from pr_agent.algo.utils import get_max_tokens
from pr_agent.algo.pr_processing import get_pr_diff

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
                # For dynamic lookups like get_settings().config.get(...)
                "config": MagicMock(),
            }

            # Configure the config object behavior
            settings_dict["config"].get.side_effect = lambda key, default=None: {
                "token_economy_mode": True,
                "max_files_in_economy_mode": 6,
            }.get(key, default)

            # Configure main get method
            mock_settings.return_value.get.side_effect = lambda key, default=None: settings_dict.get(key, default)

            # Link .config property to our configured mock
            mock_settings.return_value.config = settings_dict["config"]

            # Allow property access like get_settings().config.token_economy_mode
            mock_settings.return_value.config.token_economy_mode = True
            mock_settings.return_value.config.max_model_tokens = 32000
            mock_settings.return_value.config.custom_model_max_tokens = -1

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

        # We need to spy on get_pr_file_content to count how many times it was called with full content
        # The logic in get_diff_files calls get_pr_file_content for files within limit

        diff_files = gitlab_provider.get_diff_files()

        # In token_economy_mode=True, max_files_allowed is 6 (hardcoded currently)
        # Verify that we got all files in the list, but content loading might differ
        assert len(diff_files) == 20

        # Check how many times we loaded full content.
        # The code says:
        # if counter_valid < max_files_allowed or not diff['diff']:
        #     load full content...
        # else:
        #     content = ''

        # We provided 'diff' for all files, so it should only load full content for the first 6 files.
        # However, get_pr_file_content is called TWICE per file (old and new).
        # So we expect 6 * 2 = 12 calls.
        assert gitlab_provider.get_pr_file_content.call_count == 12

    def test_gemini_max_tokens(self, mock_settings):
        """Test that get_max_tokens returns the capped value for Gemini."""
        with patch('pr_agent.algo.utils.get_settings', mock_settings):
            max_tokens = get_max_tokens("gemini/gemini-1.5-flash")
            # Should be capped at 32000 by config.max_model_tokens
            assert max_tokens == 32000

    def test_token_economy_minimizes_context(self, gitlab_provider, mock_settings):
        """Test that token economy mode minimizes patch context in get_pr_diff."""
        # Need to patch get_settings in pr_processing as well
        with patch('pr_agent.algo.pr_processing.get_settings', mock_settings):
            gitlab_provider.get_diff_files = MagicMock(return_value=[])
            gitlab_provider.get_languages = MagicMock(return_value={})

            token_handler = MagicMock()
            token_handler.prompt_tokens = 0

            # Mock pr_generate_extended_diff to capture arguments
            with patch('pr_agent.algo.pr_processing.pr_generate_extended_diff') as mock_generate:
                mock_generate.return_value = ([], 0, [])

                get_pr_diff(gitlab_provider, token_handler, "gemini/gemini-1.5-flash")

                # Check that patch_extra_lines_before and _after were passed as 1 (economy mode)
                # instead of default (which would be higher if not in economy mode)
                args, kwargs = mock_generate.call_args
                assert kwargs['patch_extra_lines_before'] == 1
                assert kwargs['patch_extra_lines_after'] == 1
