import json
from functools import partial

from pr_agent.algo.ai_handlers.base_ai_handler import BaseAiHandler
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.config_loader import get_settings
from pr_agent.git_providers import get_git_provider_with_context
from pr_agent.log import get_logger

class PRCodeAgent:
    def __init__(self, pr_url: str, args: list = None,
                 ai_handler: partial[BaseAiHandler] = LiteLLMAIHandler):
        self.git_provider = get_git_provider_with_context(pr_url)
        self.ai_handler = ai_handler()
        self.args = args
        self.max_steps = get_settings().get("pr_code_agent.max_steps", 10)
        self.history = []

    async def run(self):
        get_logger().info("Starting PRCodeAgent")
        task = " ".join(self.args) if self.args else "No task provided."

        for _ in range(self.max_steps):
            prompt = self._build_prompt(task)
            response = await self.ai_handler.chat_completion(
                model=get_settings().config.model,
                system=get_settings().pr_code_agent.system_prompt,
                user=prompt
            )

            action_data = self._parse_response(response[0])
            if not action_data:
                break

            action = action_data.get("action")
            args = action_data.get("args", {})

            result = await self._execute_action(action, args)
            self.history.append({"action": action, "args": args, "result": result})

            if action == "finish":
                get_logger().info(f"Task finished: {result}")
                self.git_provider.publish_comment(f"Task completed: {result}")
                break

    def _build_prompt(self, task):
        from jinja2 import Template
        template = Template(get_settings().pr_code_agent.user_prompt)
        return template.render(
            task=task,
            relevant_files=self._get_relevant_files_context(),
            history=json.dumps(self.history, indent=2)
        )

    def _parse_response(self, response):
        import re
        try:
            # Try to find JSON block
            match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                # If no code block, try to find the first JSON object
                match = re.search(r"\{.*\}", response, re.DOTALL)
                if match:
                    json_str = match.group(0)
                else:
                    json_str = response
            return json.loads(json_str)
        except Exception:
            get_logger().error(f"Failed to parse JSON response: {response}")
            return None

    async def _execute_action(self, action, args):
        if action == "read_files":
            return self._read_files(args.get("file_paths", []))
        elif action == "edit_file":
            return self._edit_file(args.get("file_path"), args.get("content"))
        elif action == "finish":
            return args.get("message")
        return "Unknown action"

    def _read_files(self, file_paths):
        content = {}
        for path in file_paths:
            content[path] = self.git_provider.get_pr_file_content(path, self.git_provider.get_pr_branch())
        return content

    def _edit_file(self, file_path, content):
        self.git_provider.create_or_update_pr_file(
            file_path, self.git_provider.get_pr_branch(), content, "Agent edit"
        )
        return f"Edited {file_path}"

    def _get_relevant_files_context(self):
        try:
            files = self.git_provider.get_files()
            if not files:
                return "No files found in the repository."
            # files can be objects or strings depending on provider
            file_list = []
            for f in files:
                if hasattr(f, 'filename'):
                    file_list.append(f.filename)
                else:
                    file_list.append(str(f))
            return "\n".join(file_list[:50]) # Limit to 50 files to avoid context overflow
        except Exception as e:
            get_logger().error(f"Failed to get file list: {e}")
            return "Error fetching file list."
