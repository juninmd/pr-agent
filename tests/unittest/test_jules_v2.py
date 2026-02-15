import sys
from unittest.mock import MagicMock, patch

# PRE-IMPORT MOCKING to bypass legacy circular dependencies
mock_loguru = MagicMock()
sys.modules["loguru"] = mock_loguru

mock_pr_agent_log = MagicMock()
sys.modules["pr_agent.log"] = mock_pr_agent_log
mock_logger = MagicMock()
mock_pr_agent_log.get_logger.return_value = mock_logger

import os
import pytest

# Now import the modules under test
from pr_agent.jules.agent import JulesAgent
from pr_agent.jules.git.provider import GitProvider
from pr_agent.jules.planner import Planner

def test_jules_files_compliance():
    """Verify that all files in the new Jules module are < 150 LOC."""
    root_dir = "pr_agent/jules"
    max_lines = 150

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                with open(filepath, "r") as f:
                    lines = f.readlines()
                    if len(lines) >= max_lines:
                        pytest.fail(f"File {filepath} has {len(lines)} lines, exceeding {max_lines}")

def test_jules_agent_initialization():
    """Verify that JulesAgent initializes correctly."""
    mock_git = MagicMock(spec=GitProvider)
    mock_planner = MagicMock(spec=Planner)
    agent = JulesAgent(git_provider=mock_git, planner=mock_planner)
    assert agent.git == mock_git
    assert agent.planner == mock_planner
    mock_pr_agent_log.get_logger.assert_called()

def test_jules_planner_structure():
    """Verify Planner structure."""
    planner = Planner()
    assert hasattr(planner, "create_plan")
    assert hasattr(planner, "refine_plan")

@patch("pr_agent.jules.git.github.provider.get_settings")
@patch("pr_agent.jules.git.github.provider.Github")
def test_github_provider_structure(mock_github, mock_settings):
    """Verify GitHubProvider delegates correctly."""
    from pr_agent.jules.git.github.provider import GitHubProvider

    mock_settings.return_value.github.user_token = "dummy_token"
    provider = GitHubProvider()

    assert provider.github is not None
    assert provider.file_handler is not None
    assert provider.pr_handler is not None
    assert hasattr(provider, "get_pr_url")

def test_github_provider_init_with_repo():
    """Verify GitHubProvider initializes with repo_slug."""
    with patch("pr_agent.jules.git.github.provider.get_settings") as mock_settings, \
         patch("pr_agent.jules.git.github.provider.Github") as mock_github:

        mock_settings.return_value.github.user_token = "dummy"
        from pr_agent.jules.git.github.provider import GitHubProvider

        provider = GitHubProvider(repo_slug="owner/repo")
        mock_github.return_value.get_repo.assert_called_with("owner/repo")

@patch("pr_agent.jules.git.gitlab.provider.get_settings")
@patch("pr_agent.jules.git.gitlab.provider.gitlab.Gitlab")
def test_gitlab_provider_structure(mock_gitlab, mock_settings):
    """Verify GitLabProvider delegates correctly."""
    from pr_agent.jules.git.gitlab.provider import GitLabProvider

    mock_settings.return_value.get.return_value = "dummy"

    provider = GitLabProvider()

    assert provider.gitlab is not None
    assert provider.file_handler is not None
    assert provider.mr_handler is not None
    assert hasattr(provider, "get_pr_url")
