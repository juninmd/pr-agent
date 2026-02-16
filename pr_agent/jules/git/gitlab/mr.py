from typing import Optional
from urllib.parse import urlparse
from gitlab import GitlabError
from pr_agent.log import get_logger

class GitLabMRHandler:
    """
    Handles Merge Request interactions for GitLab.
    Strictly optimized for Clean Code and < 150 LOC.
    """
    def __init__(self, gl_client, mr_url: Optional[str] = None, project_slug: Optional[str] = None):
        self.gl = gl_client
        self.logger = get_logger()
        self.mr_url = mr_url
        self.project = None
        self.mr = None

        if mr_url:
            self._load_mr_from_url(mr_url)
        elif project_slug:
            try:
                self.project = self.gl.projects.get(project_slug)
                self.logger.info(f"Loaded Project: {project_slug}")
            except Exception as e:
                self.logger.error(f"Failed to load Project {project_slug}: {e}")
                raise e

    def _load_mr_from_url(self, mr_url: str):
        try:
            # Simple parsing: https://gitlab.com/group/project/-/merge_requests/1
            parsed = urlparse(mr_url)
            path_parts = parsed.path.strip('/').split('/')
            if 'merge_requests' not in path_parts:
                raise ValueError("Invalid MR URL")

            mr_idx = path_parts.index('merge_requests')
            mr_id = int(path_parts[mr_idx + 1])

            # Reconstruct project path. Handle /-/ separator if present
            proj_parts = path_parts[:mr_idx]
            if proj_parts and proj_parts[-1] == '-':
                proj_parts = proj_parts[:-1]

            project_path = "/".join(proj_parts)

            self.project = self.gl.projects.get(project_path)
            self.mr = self.project.mergerequests.get(mr_id)
            self.logger.info(f"Loaded MR: {project_path}!{mr_id}")
        except Exception as e:
            self.logger.error(f"Failed to load MR from {mr_url}: {e}")
            raise e

    def get_mr_url(self) -> str:
        return self.mr.web_url if self.mr else ""

    def get_project(self):
        return self.project

    def create_mr(self, project_obj, title, body, source_branch, target_branch):
        """Creates a new MR."""
        try:
            mr = project_obj.mergerequests.create({
                'source_branch': source_branch,
                'target_branch': target_branch,
                'title': title,
                'description': body
            })
            self.mr = mr
            self.mr_url = mr.web_url
            self.logger.info(f"Created MR: {mr.web_url}")
            return mr.web_url
        except GitlabError as e:
            self.logger.error(f"Failed to create MR: {e}")
            raise e

    def add_comment(self, body: str):
        """Adds a comment to the MR."""
        if not self.mr:
            self.logger.error("Cannot comment: No MR loaded.")
            return
        try:
            self.mr.notes.create({'body': body})
            self.logger.info("Added comment to MR")
        except GitlabError as e:
            self.logger.error(f"Failed to add comment: {e}")
            raise e
