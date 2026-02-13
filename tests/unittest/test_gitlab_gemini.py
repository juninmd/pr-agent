from unittest.mock import MagicMock, patch
import pytest
from pr_agent.git_providers.gitlab_provider import GitLabProvider

def get_settings_side_effect(key, default=None):
    return {
        "GITLAB.URL": "https://gitlab.com",
        "GITLAB.PERSONAL_ACCESS_TOKEN": "mock_token",
        "GITLAB.AUTH_TYPE": "oauth_token",
        "config.patch_extra_lines_before": 3,
        "config.patch_extra_lines_after": 1,
        "max_files_in_economy_mode": 6
    }.get(key, default)

def get_config_side_effect_disabled(key, default=None):
    return {
        "token_economy_mode": False,
        "max_files_in_economy_mode": 6
    }.get(key, default)

@pytest.fixture
def mock_gitlab_provider():
    with patch('pr_agent.git_providers.gitlab_provider.get_settings') as mock_settings_main, \
         patch('pr_agent.git_providers.gitlab_utils.diff_handler.get_settings') as mock_settings_diff:

        # Initial settings
        mock_settings_main.return_value.get.side_effect = get_settings_side_effect
        mock_settings_diff.return_value.get.side_effect = get_settings_side_effect

        mock_settings_main.return_value.config.get.side_effect = get_config_side_effect_disabled
        mock_settings_diff.return_value.config.get.side_effect = get_config_side_effect_disabled

        # Mock gitlab library
        with patch('pr_agent.git_providers.gitlab_provider.gitlab') as mock_gitlab_lib:
            provider = GitLabProvider("https://gitlab.com/owner/repo/merge_requests/1")
            provider.mr = MagicMock()
            yield provider, mock_settings_main

def test_token_economy_mode_disabled(mock_gitlab_provider):
    provider, mock_settings = mock_gitlab_provider
    assert mock_settings.return_value.set.call_count == 0

def test_token_economy_mode_enabled():
    with patch('pr_agent.git_providers.gitlab_provider.get_settings') as mock_settings_main, \
         patch('pr_agent.git_providers.gitlab_utils.diff_handler.get_settings') as mock_settings_diff:

        # Setup settings with token_economy_mode = True
        def side_effect(key, default=None):
            return {
                "GITLAB.URL": "https://gitlab.com",
                "GITLAB.PERSONAL_ACCESS_TOKEN": "mock_token",
                "GITLAB.AUTH_TYPE": "oauth_token",
            }.get(key, default)

        mock_settings_main.return_value.get.side_effect = side_effect
        mock_settings_diff.return_value.get.side_effect = side_effect

        # Configure config object
        config_mock = MagicMock()
        config_mock.get.side_effect = lambda key, default=None: {
            "token_economy_mode": True, # ENABLED
            "max_files_in_economy_mode": 5
        }.get(key, default)

        mock_settings_main.return_value.config = config_mock
        mock_settings_diff.return_value.config = config_mock

        with patch('pr_agent.git_providers.gitlab_provider.gitlab'):
            provider = GitLabProvider("https://gitlab.com/owner/repo/merge_requests/1")

            # Verify that settings were updated to 0 context lines
            mock_settings_main.return_value.set.assert_any_call("config.patch_extra_lines_before", 0)
            mock_settings_main.return_value.set.assert_any_call("config.patch_extra_lines_after", 0)

            # Test get_diff_files behavior
            # Mock 10 files
            changes = [{'new_path': f'file{i}.py', 'old_path': f'file{i}.py', 'diff': '...', 'new_file': False, 'deleted_file': False, 'renamed_file': False} for i in range(10)]
            provider.mr = MagicMock()
            provider.mr.changes.return_value = {'changes': changes}
            provider.mr.diffs.list.return_value = [] # simplified

            # Mock get_pr_file_content to avoid API calls
            provider.get_pr_file_content = MagicMock(return_value="content")

            # Mock filter_ignored to return all
            with patch('pr_agent.git_providers.gitlab_utils.diff_handler.filter_ignored', side_effect=lambda x, y: x):
                 with patch('pr_agent.git_providers.gitlab_utils.diff_handler.is_valid_file', return_value=True):
                    diff_files = provider.get_diff_files()

            # Should have processed all files, BUT
            # Logic:
            # if counter_valid <= max_files_allowed: load content
            # else: content = ''

            # We have 10 files. Limit is 5 (mocked above).
            # First 5 should have content. Next 5 should be empty strings.

            loaded_files = [f for f in diff_files if f.head_file == "content"]
            empty_files = [f for f in diff_files if f.head_file == ""]

            assert len(loaded_files) == 5
            assert len(empty_files) == 5
