import os
import subprocess
from pr_agent.config_loader import get_settings
from pr_agent.git_providers.git_provider import GitProvider
from pr_agent.tools.code_agent.diff_utils import apply_git_merge_diff
from pr_agent.tools.code_agent.utils import fetch_url_content

TOKEN_ECONOMY_MAX_FILE_CHARS = 10000

class AgentTools:
    """
    Tool implementation for the PRCodeAgent.
    Handles file operations, git interactions, and system commands.
    """
    def __init__(self, git_provider: GitProvider):
        self.git_provider = git_provider
        self.plan = []

    async def list_files(self, path="."):
        """Lists files in the repository."""
        try:
            cmd = ["git", "ls-files", path] if os.path.exists(".git") else ["find", path, "-maxdepth", "4", "-not", "-path", "*/.*"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout:
                return res.stdout[:5000] # Limit output
        except Exception:
            pass
        return "\n".join([f.filename for f in self.git_provider.get_files()])

    async def read_file(self, file_path):
        """Reads file content from the PR branch."""
        content = self.git_provider.get_pr_file_content(file_path, self.git_provider.get_pr_branch())
        if get_settings().config.get("token_economy_mode", False):
            limit = TOKEN_ECONOMY_MAX_FILE_CHARS
            if len(content) > limit:
                content = content[:limit] + f"\n...(truncated, content > {limit} chars due to token_economy_mode)"
        return content

    async def edit_file(self, file_path, content):
        """Edits or creates a file in the PR branch."""
        self.git_provider.create_or_update_pr_file(
            file_path, self.git_provider.get_pr_branch(), content, "Agent edit"
        )
        if os.path.exists(file_path) or os.path.exists(".git"):
            try:
                if os.path.dirname(file_path):
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w") as f:
                    f.write(content)
            except Exception:
                pass
        return f"Edited {file_path}"

    async def delete_file(self, file_path):
        """Deletes a file from the PR branch."""
        try:
            self.git_provider.delete_file(file_path, self.git_provider.get_pr_branch(), "Agent deleted file")
        except Exception as e:
            return f"Error deleting {file_path} from remote: {e}"
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        return f"Deleted {file_path}"

    async def rename_file(self, filepath, new_filepath):
        """Renames a file."""
        content = await self.read_file(filepath)
        await self.edit_file(new_filepath, content)
        await self.delete_file(filepath)
        return f"Renamed {filepath} to {new_filepath}"

    async def replace_with_git_merge_diff(self, filepath, merge_diff):
        """Applies a git merge diff to a file."""
        content = await self.read_file(filepath)
        new_content = apply_git_merge_diff(content, merge_diff)
        await self.edit_file(filepath, new_content)
        return f"Applied diff to {filepath}"

    async def run_in_bash_session(self, command):
        """Runs a bash command."""
        try:
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
            return f"Stdout: {res.stdout}\nStderr: {res.stderr}"
        except Exception as e:
            return f"Error: {e}"

    async def set_plan(self, plan):
        self.plan = plan
        return "Plan set."

    async def plan_step_complete(self, message):
        return f"Step completed: {message}"

    async def request_plan_review(self, plan):
        return "Plan review requested. (Simulated auto-approval)"

    async def request_code_review(self):
        return "Code review requested. (Simulated auto-approval)"

    async def view_image(self, url):
        return f"Image viewed: {url}"

    async def view_text_website(self, url):
        return await fetch_url_content(url)

    async def finish(self, message):
        return f"Task completed: {message}"
