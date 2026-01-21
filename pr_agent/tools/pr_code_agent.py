import json
import re
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.config_loader import get_settings
from pr_agent.git_providers import get_git_provider_with_context
from pr_agent.log import get_logger
from pr_agent.tools.code_agent.tool_registry import ToolRegistry
from pr_agent.tools.code_agent.tools import AgentTools
from pr_agent.tools.code_agent.prompts import PromptGenerator

class PRCodeAgent:
    def __init__(self, pr_url: str, args: list = None, ai_handler=LiteLLMAIHandler):
        self.git_provider = get_git_provider_with_context(pr_url)
        self.ai_handler = ai_handler()
        self.args = args or []
        self.max_steps = get_settings().get("pr_code_agent.max_steps", 15)
        self.tools = AgentTools(self.git_provider)
        self.registry = ToolRegistry(self.git_provider)
        self._register_tools()
        self.prompts = PromptGenerator(self.registry.get_tool_definitions())

    def _register_tools(self):
        t = self.tools
        r = self.registry
        r.register_tool("list_files", "List files in repo", t.list_files)
        r.register_tool("read_file", "Read file content", t.read_file)
        r.register_tool("edit_file", "Edit file content", t.edit_file)
        r.register_tool("delete_file", "Delete file", t.delete_file)
        r.register_tool("set_plan", "Set the plan", t.set_plan)
        r.register_tool("plan_step_complete", "Mark step complete", t.plan_step_complete)
        r.register_tool("run_in_bash_session", "Run bash command", t.run_in_bash_session)
        r.register_tool("finish", "Finish task", t.finish)

    async def run(self):
        get_logger().info("Starting Autonomous PRCodeAgent")
        task = " ".join(self.args) if self.args else "Perform task."
        history = []
        for i in range(self.max_steps):
            sys_p = self.prompts.build_system_prompt()
            usr_p = self.prompts.build_user_prompt(task, history)
            resp = await self.ai_handler.chat_completion(
                model=get_settings().config.model, system=sys_p, user=usr_p
            )
            action = self._parse_response(resp[0])
            if not action:
                get_logger().warning("Failed to parse action from response")
                continue

            res = await self.registry.execute(action.get("action"), action.get("args", {}))
            history.append({"action": action.get("action"), "result": str(res)})

            if action.get("action") == "finish":
                msg = action.get("args", {}).get("message", "Done")
                self.git_provider.publish_comment(f"Task Done: {msg}")
                break

    def _parse_response(self, response):
        try:
            match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            json_str = match.group(1) if match else response
            # Basic cleanup for potential trailing commas or markdown issues
            json_str = json_str.strip()
            return json.loads(json_str)
        except Exception as e:
            get_logger().warning(f"JSON Parse Error: {e}")
            return None
