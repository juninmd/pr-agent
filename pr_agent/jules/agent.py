import json
from pr_agent.jules.planner import Planner
from pr_agent.jules.tools import JulesTools
from pr_agent.jules.state import State
from pr_agent.log import get_logger

class JulesAgent:
    """
    Autonomous AI Coding Agent (Jules).
    Follows Plan -> Act -> Verify -> Reflect loop.
    Strictly optimized for Clean Code and < 150 LOC.
    """
    def __init__(self, git_provider):
        self.tools = JulesTools(git_provider)
        self.planner = Planner()
        self.logger = get_logger()

    async def run(self, task: str):
        self.logger.info(f"Jules starting task: {task}")
        state = State(task=task)
        files_str = await self.tools.list_files()
        state.files = files_str.split('\n') if files_str else []

        plan = await self.planner.create_plan(task, state.get_context())

        i = 0
        while i < len(plan.steps):
            step = plan.steps[i]
            self.logger.info(f"Step {i+1}/{len(plan.steps)}: {step.description}")

            result = await self._execute_step(step, state)
            state.add_history(step.description, step.command, result)

            # Simple Reflection: Check for errors
            if "Error" in result:
                self.logger.warning(f"Step failed: {result}. Refining plan...")
                plan = await self.planner.refine_plan(plan, result)
                # Retry current step index (ensure within bounds)
                i = min(i, len(plan.steps) - 1)
                if i < 0: i = 0
                continue

            i += 1

        return "Task Completed"

    async def _execute_step(self, step, state) -> str:
        prompt = (
            f"Context:\n{state.get_context()}\n"
            f"Current Step: {step.description}\nHint: {step.command}\n"
            "Tools: read_file, edit_file, delete_file, list_files, search_files, run_command.\n"
            "Return ONLY a JSON object: {'tool': 'name', 'args': {...}}"
        )
        try:
            resp, _ = await self.planner.ai.chat_completion(
                model=self.planner.model, system="You are a tool caller.", user=prompt
            )
            return await self._parse_tool_call(resp)
        except Exception as e:
            return f"Error executing step: {e}"

    async def _parse_tool_call(self, response: str) -> str:
        try:
            if "```json" in response: response = response.split("```json")[1].split("```")[0]
            elif "```" in response: response = response.split("```")[1].split("```")[0]

            call = json.loads(response.strip())
            tool_name = call.get('tool')
            args = call.get('args', {})

            if hasattr(self.tools, tool_name):
                func = getattr(self.tools, tool_name)
                # Ensure args is a dict
                if not isinstance(args, dict):
                     return f"Error: Tool arguments must be a dictionary."
                return await func(**args)
            return f"Error: Tool {tool_name} not found."
        except Exception as e:
            return f"Tool parsing error: {e}"
