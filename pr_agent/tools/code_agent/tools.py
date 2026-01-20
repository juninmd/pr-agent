import json
import os
import subprocess
from pr_agent.git_providers.git_provider import GitProvider

class AgentTools:
    def __init__(self, git_provider: GitProvider):
        self.git_provider = git_provider
        self.plan = []
        self.plan_status = {}

    async def list_files(self, path="."):
        files = self.git_provider.get_files()
        file_list = []
        for f in files:
            name = f.filename if hasattr(f, 'filename') else str(f)
            if name.startswith(path):
                file_list.append(name)
        return "\n".join(file_list)

    async def read_file(self, file_path):
        return self.git_provider.get_pr_file_content(file_path, self.git_provider.get_pr_branch())

    async def edit_file(self, file_path, content):
        self.git_provider.create_or_update_pr_file(
            file_path, self.git_provider.get_pr_branch(), content, "Agent edit"
        )
        return f"Edited {file_path}"

    async def set_plan(self, plan):
        self.plan = plan
        return "Plan set."

    async def plan_step_complete(self, message):
        self.plan_status[len(self.plan_status) + 1] = message
        return f"Step completed: {message}"

    async def run_in_bash_session(self, command):
        # Warning: This runs in the environment where the agent is executing.
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=60
            )
            return f"Stdout: {result.stdout}\nStderr: {result.stderr}"
        except Exception as e:
            return f"Error running command: {e}"

    async def finish(self, message):
        return f"Task completed: {message}"
