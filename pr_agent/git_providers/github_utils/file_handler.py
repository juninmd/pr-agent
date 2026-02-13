from pr_agent.log import get_logger
from pr_agent.git_providers.git_provider import FilePatchInfo

class GithubFileHandler:
    def __init__(self, provider):
        self.provider = provider

    def get_pr_file_content(self, file_path: str, branch: str) -> str:
        try:
            file_content_str = str(
                self.provider._get_repo()
                .get_contents(file_path, ref=branch)
                .decoded_content.decode()
            )
        except Exception:
            file_content_str = ""
        return file_content_str

    def create_or_update_pr_file(
        self, file_path: str, branch: str, contents="", message=""
    ) -> None:
        try:
            file_obj = self.provider._get_repo().get_contents(file_path, ref=branch)
            sha1=file_obj.sha
        except Exception:
            sha1=""
        self.provider.repo_obj.update_file(
            path=file_path,
            message=message,
            content=contents,
            sha=sha1,
            branch=branch,
        )

    def delete_file(self, file_path: str, branch: str, message: str = "Delete file") -> None:
        try:
            file_obj = self.provider._get_repo().get_contents(file_path, ref=branch)
            self.provider.repo_obj.delete_file(
                path=file_path,
                message=message,
                sha=file_obj.sha,
                branch=branch,
            )
        except Exception as e:
            get_logger().error(f"Failed to delete file {file_path}: {e}")
            raise

    def get_file_content_from_obj(self, file: FilePatchInfo, sha: str) -> str:
        return self.get_pr_file_content(file.filename, sha)
