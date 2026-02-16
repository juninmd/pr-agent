from typing import List, Optional
import gitlab
from pr_agent.config_loader import get_settings
from pr_agent.jules.git.provider import GitProvider
from pr_agent.log import get_logger

class GitLabProvider(GitProvider):
    """
    Optimized GitLab Provider.
    Delegates strictly to specialized handlers to maintain < 150 LOC.
    """
    def __init__(self, mr_url: Optional[str] = None, project_slug: Optional[str] = None):
        self.gl = self._get_client()
        self.logger = get_logger()

        # Lazy import to avoid circular dependency issues
        from pr_agent.jules.git.gitlab.files import GitLabFileHandler
        from pr_agent.jules.git.gitlab.mr import GitLabMRHandler

        self.file_handler = GitLabFileHandler(self.gl)
        self.mr_handler = GitLabMRHandler(self.gl, mr_url, project_slug)

    def _get_client(self):
        url = get_settings().get("GITLAB.URL", "https://gitlab.com")
        token = get_settings().get("GITLAB.PERSONAL_ACCESS_TOKEN", None)
        ssl_verify = get_settings().get("GITLAB.SSL_VERIFY", True)
        if not token:
            raise ValueError("GitLab token not set in configuration")
        return gitlab.Gitlab(url=url, private_token=token, ssl_verify=ssl_verify)

    def get_pr_url(self) -> str:
        return self.mr_handler.get_mr_url()

    def get_current_branch(self) -> str:
        return self.mr_handler.mr.source_branch if self.mr_handler.mr else "main"

    def get_files(self) -> List[str]:
        return self.file_handler.get_files(self.mr_handler.mr)

    def get_file_content(self, file_path: str, branch: Optional[str] = None) -> str:
        project = self.mr_handler.get_project()
        return self.file_handler.get_content(project, file_path, branch)

    def create_or_update_file(self, file_path: str, content: str, message: str, branch: str) -> None:
        project = self.mr_handler.get_project()
        self.file_handler.create_or_update(project, file_path, content, message, branch)

    def delete_file(self, file_path: str, message: str, branch: str) -> None:
        project = self.mr_handler.get_project()
        self.file_handler.delete_file(project, file_path, message, branch)

    def create_pr(self, title: str, body: str, source_branch: str, target_branch: str) -> str:
        project = self.mr_handler.get_project()
        return self.mr_handler.create_mr(project, title, body, source_branch, target_branch)

    def add_comment(self, body: str) -> None:
        self.mr_handler.add_comment(body)
