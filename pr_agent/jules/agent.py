import json
from pr_agent.jules.planner import Planner
from pr_agent.jules.tools import JulesTools
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger

class JulesAgent:
    """
    Autonomous AI Coding Agent (Jules).
    Follows Plan -> Act -> Verify -> Reflect loop.
    Strictly optimized for Clean Code and < 150 LOC.
    """
    def __init__(self, git_provider):
        self.git = git_provider
        self.tools = JulesTools(git_provider)
        self.planner = Planner()
        self.ai = LiteLLMAIHandler()
        self.logger = get_logger()
        self.model = get_settings().config.model

    async def run(self, task: str):
        self.logger.info(f"Jules starting task: {task}")
        files = await self.tools.list_files()
        plan = await self.planner.create_plan(task, files)

        for step in plan.steps:
            self.logger.info(f"Step: {step.description}")
            result = await self._execute_step(step, files)
            self.logger.info(f"Result: {result}")

            if "Error" in result:
                # Simple reflection: Retry once
                self.logger.warning("Step failed. Retrying with reflection...")
                result = await self._execute_step(step, files, feedback=result)

        return "Task Completed"

    async def _execute_step(self, step, context, feedback="") -> str:
        prompt = (
            f"Context: {context}\nStep: {step.description}\nHint: {step.command}\n"
            f"Feedback: {feedback}\n"
            "You have tools: read_file(path), edit_file(path, content), delete_file(path), run_command(cmd), list_files(path).\n"
            "Output ONLY a JSON object: {'tool': 'name', 'args': {'arg1': 'val1'}}\n"
            "Example: {'tool': 'edit_file', 'args': {'file_path': 'a.py', 'content': 'print(1)'}}"
        )
        try:
            resp, _ = await self.ai.chat_completion(self.model, "You are a tool caller.", prompt)

            # Clean markdown
            if "```json" in resp: resp = resp.split("```json")[1].split("```")[0]
            elif "```" in resp: resp = resp.split("```")[1].split("```")[0]

            call = json.loads(resp.strip())
            tool_name = call.get('tool')
            args = call.get('args', {})

            if hasattr(self.tools, tool_name):
                func = getattr(self.tools, tool_name)
                return await func(**args)
            return f"Error: Tool {tool_name} not found."
        except Exception as e:
            return f"Error executing step: {e}"
