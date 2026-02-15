import base64
from gitlab import GitlabError
from pr_agent.log import get_logger

class GitLabFileHandler:
    """
    Handles file operations for GitLab.
    Strictly optimized for Clean Code and < 150 LOC.
    """
    def __init__(self, gitlab_client):
        self.gitlab = gitlab_client
        self.logger = get_logger()

    def get_files(self, mr_obj):
        """Returns a list of files changed in the MR."""
        if not mr_obj: return []
        changes = mr_obj.changes()
        return [f['new_path'] for f in changes.get('changes', [])]

    def get_content(self, project_obj, file_path, branch=None):
        """Retrieves file content."""
        if not project_obj: raise ValueError("Project object required")
        try:
            ref = branch or project_obj.default_branch
            file_obj = project_obj.files.get(file_path=file_path, ref=ref)
            return base64.b64decode(file_obj.content).decode("utf-8")
        except GitlabError as e:
            if e.response_code == 404:
                self.logger.warning(f"File {file_path} not found in branch {branch}")
                return None
            self.logger.error(f"Error fetching file {file_path}: {e}")
            raise e

    def create_or_update(self, project_obj, file_path, content, message, branch):
        """Creates or updates a file."""
        if not project_obj: raise ValueError("Project object required")
        try:
            try:
                # Update existing file
                f = project_obj.files.get(file_path=file_path, ref=branch)
                f.content = content
                f.save(branch=branch, commit_message=message)
                self.logger.info(f"Updated file {file_path} on branch {branch}")
            except GitlabError as e:
                if e.response_code == 404:
                    # Create new file
                    project_obj.files.create({
                        'file_path': file_path,
                        'branch': branch,
                        'content': content,
                        'commit_message': message
                    })
                    self.logger.info(f"Created file {file_path} on branch {branch}")
                else:
                    raise e
        except Exception as e:
            self.logger.error(f"Failed to write file {file_path}: {e}")
            raise e
