from github import GithubException
from pr_agent.log import get_logger

class GitHubFileHandler:
    """
    Handles file operations for GitHub.
    Strictly optimized for Clean Code and < 150 LOC.
    """
    def __init__(self, github_client):
        self.github = github_client
        self.logger = get_logger()

    def get_files(self, pr_obj):
        """Returns a list of files changed in the PR."""
        if not pr_obj: return []
        return [f.filename for f in pr_obj.get_files()]

    def get_content(self, repo_obj, file_path, branch=None):
        """Retrieves file content."""
        if not repo_obj: raise ValueError("Repo object required")
        try:
            kwargs = {"ref": branch} if branch else {}
            content_file = repo_obj.get_contents(file_path, **kwargs)

            # Handle case where path is a directory
            if isinstance(content_file, list):
                self.logger.warning(f"Path {file_path} is a directory, not a file.")
                raise IsADirectoryError(f"Path {file_path} points to a directory")

            return content_file.decoded_content.decode("utf-8")
        except GithubException as e:
            if e.status == 404:
                self.logger.warning(f"File {file_path} not found in branch {branch}")
                return None # File not found
            self.logger.error(f"Error fetching file {file_path}: {e}")
            raise e

    def create_or_update(self, repo_obj, file_path, content, message, branch):
        """Creates or updates a file."""
        if not repo_obj: raise ValueError("Repo object required")
        try:
            # Check if file exists to get SHA for update
            try:
                current_file = repo_obj.get_contents(file_path, ref=branch)
                repo_obj.update_file(
                    file_path, message, content, current_file.sha, branch=branch
                )
                self.logger.info(f"Updated file {file_path} on branch {branch}")
            except GithubException as e:
                if e.status == 404:
                    # File doesn't exist, create it
                    repo_obj.create_file(file_path, message, content, branch=branch)
                    self.logger.info(f"Created file {file_path} on branch {branch}")
                else:
                    raise e
        except Exception as e:
            self.logger.error(f"Failed to write file {file_path}: {e}")
            raise e
