from typing import List, Optional
from github import Github, Auth
from pr_agent.config_loader import get_settings
from pr_agent.jules.git.provider import GitProvider

class GitHubProvider(GitProvider):
    """
    Optimized GitHub Provider.
    Delegates strictly to specialized handlers to maintain < 150 LOC.
    """
    def __init__(self, pr_url: Optional[str] = None, repo_slug: Optional[str] = None):
        self.github = self._get_client()

        # Lazy import to avoid circular dependency issues
        from pr_agent.jules.git.github.files import GitHubFileHandler
        from pr_agent.jules.git.github.pr import GitHubPRHandler

        self.file_handler = GitHubFileHandler(self.github)
        self.pr_handler = GitHubPRHandler(self.github, pr_url, repo_slug)

    def _get_client(self):
        token = get_settings().github.user_token
        return Github(auth=Auth.Token(token))

    def get_pr_url(self) -> str:
        return self.pr_handler.get_pr_url()

    def get_files(self) -> List[str]:
        return self.file_handler.get_files(self.pr_handler.pr)

    def get_file_content(self, file_path: str, branch: Optional[str] = None) -> str:
        repo = self.pr_handler.get_repo()
        return self.file_handler.get_content(repo, file_path, branch)

    def create_or_update_file(self, file_path: str, content: str, message: str, branch: str) -> None:
        repo = self.pr_handler.get_repo()
        self.file_handler.create_or_update(repo, file_path, content, message, branch)

    def create_pr(self, title: str, body: str, source_branch: str, target_branch: str) -> str:
        repo = self.pr_handler.get_repo()
        return self.pr_handler.create_pr(repo, title, body, source_branch, target_branch)

    def add_comment(self, body: str) -> None:
        self.pr_handler.add_comment(body)
