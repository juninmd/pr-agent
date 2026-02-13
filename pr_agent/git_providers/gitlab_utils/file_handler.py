from gitlab import GitlabGetError, GitlabAuthenticationError, GitlabCreateError, GitlabUpdateError
from pr_agent.log import get_logger
from pr_agent.algo.git_patch_processing import decode_if_bytes

class GitLabFileHandler:
    def __init__(self, provider):
        self.provider = provider

    def get_pr_file_content(self, file_path: str, branch: str) -> str:
        try:
            file_obj = self.provider.gl.projects.get(self.provider.id_project).files.get(file_path, branch)
            content = file_obj.decode()
            return decode_if_bytes(content)
        except GitlabGetError:
            return ''
        except Exception as e:
            get_logger().warning(f"Error retrieving file {file_path} from branch {branch}: {e}")
            return ''

    def create_or_update_pr_file(self, file_path: str, branch: str, contents="", message="") -> None:
        try:
            project = self.provider.gl.projects.get(self.provider.id_project)
            if not message:
                action = "Update" if contents else "Create"
                message = f"{action} {file_path}"

            try:
                existing_file = project.files.get(file_path, branch)
                existing_file.content = contents
                existing_file.save(branch=branch, commit_message=message)
                get_logger().debug(f"Updated file {file_path} in branch {branch}")
            except GitlabGetError:
                project.files.create({
                    'file_path': file_path,
                    'branch': branch,
                    'content': contents,
                    'commit_message': message
                })
                get_logger().debug(f"Created file {file_path} in branch {branch}")
        except GitlabAuthenticationError as e:
            get_logger().error(f"Authentication failed while creating/updating file {file_path} in branch {branch}: {e}")
            raise
        except (GitlabCreateError, GitlabUpdateError) as e:
            get_logger().error(f"Permission denied or validation error for file {file_path} in branch {branch}: {e}")
            raise
        except Exception as e:
            get_logger().exception(f"Unexpected error creating/updating file {file_path} in branch {branch}: {e}")
            raise

    def delete_file(self, file_path: str, branch: str, message: str = "Delete file") -> None:
        try:
            project = self.provider.gl.projects.get(self.provider.id_project)
            project.files.delete(file_path=file_path, branch=branch, commit_message=message)
            get_logger().debug(f"Deleted file {file_path} in branch {branch}")
        except Exception as e:
            get_logger().error(f"Failed to delete file {file_path}: {e}")
            raise
