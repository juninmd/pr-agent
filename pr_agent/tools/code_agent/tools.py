import os
import subprocess
from pr_agent.config_loader import get_settings
from pr_agent.git_providers.git_provider import GitProvider

TOKEN_ECONOMY_MAX_FILE_CHARS = 10000

class AgentTools:
    def __init__(self, git_provider: GitProvider):
        self.git_provider = git_provider
        self.plan = []

    async def list_files(self, path="."):
        try:
            cmd = ["git", "ls-files", path] if os.path.exists(".git") else ["find", path, "-maxdepth", "4", "-not", "-path", "*/.*"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout:
                return res.stdout[:5000] # Limit output
        except Exception:
            pass
        return "\n".join([f.filename for f in self.git_provider.get_files()])

    async def read_file(self, file_path):
        content = self.git_provider.get_pr_file_content(file_path, self.git_provider.get_pr_branch())
        if get_settings().config.get("token_economy_mode", False):
            limit = TOKEN_ECONOMY_MAX_FILE_CHARS
            if len(content) > limit:
                content = content[:limit] + f"\n...(truncated, content > {limit} chars due to token_economy_mode)"
        return content

    async def edit_file(self, file_path, content):
        self.git_provider.create_or_update_pr_file(
            file_path, self.git_provider.get_pr_branch(), content, "Agent edit"
        )
        return f"Edited {file_path}"

    async def delete_file(self, file_path):
        try:
            if os.path.exists(file_path):
                os.remove(file_path) # Local delete for tests
            # Note: Provider API usually doesn't support delete yet via common interface
            return f"Deleted {file_path} (locally if present)"
        except Exception as e:
            return f"Error deleting: {e}"

    async def run_in_bash_session(self, command):
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

    async def finish(self, message):
        return f"Task completed: {message}"
