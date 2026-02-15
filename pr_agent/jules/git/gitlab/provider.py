from typing import List, Optional
import gitlab
from pr_agent.config_loader import get_settings
from pr_agent.jules.git.provider import GitProvider

class GitLabProvider(GitProvider):
    """
    Optimized GitLab Provider.
    Delegates strictly to specialized handlers to maintain < 150 LOC.
    """
    def __init__(self, pr_url: Optional[str] = None, repo_slug: Optional[str] = None):
        self.gitlab = self._get_client()

        # Lazy import to avoid circular dependency issues
        from pr_agent.jules.git.gitlab.files import GitLabFileHandler
        from pr_agent.jules.git.gitlab.mr import GitLabMRHandler

        self.file_handler = GitLabFileHandler(self.gitlab)
        self.mr_handler = GitLabMRHandler(self.gitlab, pr_url, repo_slug)

    def _get_client(self):
        url = get_settings().get("GITLAB.URL", "https://gitlab.com")
        token = get_settings().get("GITLAB.PERSONAL_ACCESS_TOKEN", None)
        return gitlab.Gitlab(url, private_token=token)

    def get_pr_url(self) -> str:
        return self.mr_handler.get_mr_url()

    def get_files(self) -> List[str]:
        return self.file_handler.get_files(self.mr_handler.mr)

    def get_file_content(self, file_path: str, branch: Optional[str] = None) -> str:
        project = self.mr_handler.get_project()
        return self.file_handler.get_content(project, file_path, branch)

    def create_or_update_file(self, file_path: str, content: str, message: str, branch: str) -> None:
        project = self.mr_handler.get_project()
        self.file_handler.create_or_update(project, file_path, content, message, branch)

    def create_pr(self, title: str, body: str, source_branch: str, target_branch: str) -> str:
        project = self.mr_handler.get_project()
        return self.mr_handler.create_mr(project, title, body, source_branch, target_branch)

    def add_comment(self, body: str) -> None:
        self.mr_handler.add_comment(body)
