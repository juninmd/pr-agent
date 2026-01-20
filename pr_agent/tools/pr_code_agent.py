from pr_agent.algo.ai_handlers.base_ai_handler import BaseAiHandler
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.config_loader import get_settings
from pr_agent.git_providers import get_git_provider_with_context
from pr_agent.log import get_logger
from pr_agent.tools.code_agent.tool_registry import ToolRegistry
from pr_agent.tools.code_agent.tools import AgentTools

class PRCodeAgent:
    def __init__(self, pr_url: str, args: list = None, ai_handler=LiteLLMAIHandler):
        self.git_provider = get_git_provider_with_context(pr_url)
        self.ai_handler = ai_handler()
        self.args = args
        self.max_steps = get_settings().get("pr_code_agent.max_steps", 15)
        self.tools = AgentTools(self.git_provider)
        self.registry = ToolRegistry(self.git_provider)
        self._register_tools()

    def _register_tools(self):
        self.registry.register_tool("list_files", "List files", self.tools.list_files)
        self.registry.register_tool("read_file", "Read file content", self.tools.read_file)
        self.registry.register_tool("edit_file", "Edit file content", self.tools.edit_file)
        self.registry.register_tool("set_plan", "Set the plan", self.tools.set_plan)
        self.registry.register_tool("plan_step_complete", "Mark step complete", self.tools.plan_step_complete)
        self.registry.register_tool("run_in_bash_session", "Run bash command", self.tools.run_in_bash_session)
        self.registry.register_tool("finish", "Finish task", self.tools.finish)

    async def run(self):
        get_logger().info("Starting PRCodeAgent (Jules-like)")
        task = " ".join(self.args) if self.args else "No task provided."
        history = []
        for _ in range(self.max_steps):
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(task, history)
            response = await self.ai_handler.chat_completion(
                model=get_settings().config.model,
                system=system_prompt,
                user=user_prompt
            )
            action_data = self._parse_response(response[0])
            if not action_data:
                get_logger().warning(f"Failed to parse response: {response[0]}")
                continue # Retry or skip to next iteration
            result = await self.registry.execute(action_data.get("action"), action_data.get("args", {}))
            history.append({"action": action_data.get("action"), "result": result})
            if action_data.get("action") == "finish":
                self.git_provider.publish_comment(f"Task completed: {action_data.get('args', {}).get('message')}")
                break

    def _build_system_prompt(self):
        from jinja2 import Template
        return Template(get_settings().pr_code_agent.system_prompt).render(
            tools=self.registry.get_tool_definitions()
        )

    def _build_user_prompt(self, task, history):
        from jinja2 import Template
        return Template(get_settings().pr_code_agent.user_prompt).render(
            task=task, history=history
        )

    def _parse_response(self, response):
        import json, re
        try:
            match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            return json.loads(match.group(1)) if match else json.loads(response)
        except: return None
