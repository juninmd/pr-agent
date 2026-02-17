import json
from dataclasses import dataclass
from typing import List
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger

@dataclass
class Step:
    description: str
    command: str = ""

@dataclass
class Plan:
    steps: List[Step]
    goal: str

class Planner:
    """
    AI Planner for Jules.
    Generates execution plans using LLM.
    Strictly optimized for Clean Code and < 150 LOC.
    """
    def __init__(self):
        self.ai = LiteLLMAIHandler()
        self.logger = get_logger()
        self.model = get_settings().config.model

    async def create_plan(self, task: str, file_context: str) -> Plan:
        """Generates a plan based on the task."""
        system_prompt = (
            "You are an autonomous software engineer. Create a step-by-step plan to solve the user's task.\n"
            "Think step-by-step. Verify your assumptions.\n"
            "Return ONLY a JSON object: {'steps': [{'description': '...', 'command': '...'}, ...]}\n"
            "Commands should be concise hints for the agent (e.g., 'edit_file src/main.py ...')."
        )
        user_prompt = f"Task: {task}\n\nContext Files:\n{file_context}"
        response, _ = await self.ai.chat_completion(
            model=self.model, system=system_prompt, user=user_prompt
        )
        return self._parse_response(response, task)

    async def refine_plan(self, current_plan: Plan, feedback: str) -> Plan:
        """Refines plan based on feedback."""
        system_prompt = (
            "You are a Senior Engineer refining a plan based on execution feedback.\n"
            "Update steps to fix errors or adjust strategy.\n"
            "Return ONLY a JSON object: {'steps': [{'description': '...', 'command': '...'}, ...]}"
        )
        user_prompt = (
            f"Original Goal: {current_plan.goal}\n"
            f"Feedback: {feedback}\n"
            f"Current Steps: {[s.description for s in current_plan.steps]}"
        )
        response, _ = await self.ai.chat_completion(
            model=self.model, system=system_prompt, user=user_prompt
        )
        return self._parse_response(response, current_plan.goal)

    def _parse_response(self, response: str, goal: str) -> Plan:
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            data = json.loads(response.strip())
            steps = [Step(description=s.get('description', ''), command=s.get('command', '')) for s in data.get('steps', [])]
            return Plan(steps=steps, goal=goal)
        except Exception as e:
            self.logger.error(f"Failed to parse plan: {e}")
            return Plan(steps=[Step(description=f"Manual intervention required: {goal}")], goal=goal)
