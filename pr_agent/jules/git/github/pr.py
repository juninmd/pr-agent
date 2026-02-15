from typing import Optional
from github import GithubException
from pr_agent.log import get_logger
from pr_agent.git_providers.github_utils.url_parser import GithubURLParser

class GitHubPRHandler:
    """
    Handles PR interactions for GitHub.
    Strictly optimized for Clean Code and < 150 LOC.
    """
    def __init__(self, github_client, pr_url: Optional[str] = None, repo_slug: Optional[str] = None):
        self.github = github_client
        self.logger = get_logger()
        self.pr_url = pr_url
        self.repo = None
        self.pr = None

        if pr_url:
            self._load_pr_from_url(pr_url)
        elif repo_slug:
            try:
                self.repo = self.github.get_repo(repo_slug)
                self.logger.info(f"Loaded Repo: {repo_slug}")
            except Exception as e:
                self.logger.error(f"Failed to load Repo {repo_slug}: {e}")
                raise e

    def _load_pr_from_url(self, pr_url: str):
        try:
            repo_name, pr_number = GithubURLParser.parse_pr_url(pr_url)
            self.repo = self.github.get_repo(repo_name)
            self.pr = self.repo.get_pull(int(pr_number))
            self.logger.info(f"Loaded PR: {repo_name}#{pr_number}")
        except Exception as e:
            self.logger.error(f"Failed to load PR from {pr_url}: {e}")
            raise e

    def get_pr_url(self) -> str:
        return self.pr.html_url if self.pr else ""

    def get_repo(self):
        return self.repo

    def create_pr(self, repo_obj, title, body, source_branch, target_branch):
        """Creates a new PR."""
        try:
            pr = repo_obj.create_pull(
                title=title, body=body, head=source_branch, base=target_branch
            )
            self.pr = pr
            self.pr_url = pr.html_url
            self.logger.info(f"Created PR: {pr.html_url}")
            return pr.html_url
        except GithubException as e:
            self.logger.error(f"Failed to create PR: {e}")
            raise e

    def add_comment(self, body: str):
        """Adds a comment to the PR."""
        if not self.pr:
            self.logger.error("Cannot comment: No PR loaded.")
            return
        try:
            self.pr.create_issue_comment(body)
            self.logger.info("Added comment to PR")
        except GithubException as e:
            self.logger.error(f"Failed to add comment: {e}")
            raise e
