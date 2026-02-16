import os
import subprocess
from pr_agent.jules.git.provider import GitProvider
from pr_agent.log import get_logger

class JulesTools:
    """
    Tools for Jules Agent.
    Handles File System and Execution.
    Strictly optimized for Clean Code and < 150 LOC.
    """
    def __init__(self, git_provider: GitProvider):
        self.git = git_provider
        self.logger = get_logger()

    async def list_files(self, path=".") -> str:
        """Lists files in the repository."""
        cmd = ["git", "ls-files"] if os.path.exists(".git") else ["find", path, "-maxdepth", "4", "-not", "-path", "*/.*"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                files = res.stdout.strip().split('\n')
                return "\n".join(files[:1000]) # Limit to 1000 files
            return "Error listing files."
        except Exception as e:
            self.logger.warning(f"Error listing files: {e}")
            return str(e)

    async def read_file(self, file_path: str) -> str:
        """Reads a file from the repository."""
        try:
            # Try reading locally first for speed/latest state
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    return f.read()
            # Fallback to git provider
            return self.git.get_file_content(file_path)
        except Exception as e:
            return f"Error reading {file_path}: {e}"

    async def edit_file(self, file_path: str, content: str) -> str:
        """Creates or updates a file."""
        try:
            # Update locally
            if os.path.dirname(file_path):
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)

            # Update remote
            branch = self.git.get_current_branch()
            self.git.create_or_update_file(file_path, content, "Jules update", branch)

            return f"Successfully edited {file_path}"
        except Exception as e:
            return f"Error editing {file_path}: {e}"

    async def delete_file(self, file_path: str) -> str:
        """Deletes a file."""
        try:
            # Delete locally
            if os.path.exists(file_path):
                os.remove(file_path)

            # Delete remote
            branch = self.git.get_current_branch()
            self.git.delete_file(file_path, "Jules delete", branch)

            return f"Successfully deleted {file_path}"
        except Exception as e:
            return f"Error deleting {file_path}: {e}"

    async def run_command(self, command: str) -> str:
        """Runs a bash command."""
        try:
            # nosec B602: shell=True required for complex commands
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60) # nosec B602
            return f"Stdout: {res.stdout}\nStderr: {res.stderr}"
        except Exception as e:
            return f"Execution Error: {e}"
