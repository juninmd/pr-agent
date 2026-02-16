import json
from dataclasses import dataclass, field
from typing import List
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger

@dataclass
class Step:
    description: str
    command: str = "" # Optional command hint

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
            "Return ONLY a JSON object with the format: {'steps': [{'description': '...', 'command': '...'}, ...]}\n"
            "Commands should be bash commands or 'edit_file ...'. Keep it simple."
        )
        user_prompt = f"Task: {task}\n\nContext Files:\n{file_context}"

        response, _ = await self.ai.chat_completion(
            model=self.model, system=system_prompt, user=user_prompt
        )

        return self._parse_response(response, task)

    async def refine_plan(self, plan: Plan, feedback: str) -> Plan:
        """Refines plan based on feedback."""
        system_prompt = "You are refining a plan based on execution feedback. Update steps to fix errors."
        user_prompt = f"Original Goal: {plan.goal}\nFeedback: {feedback}\nCurrent Steps: {[s.description for s in plan.steps]}"

        response, _ = await self.ai.chat_completion(
            model=self.model, system=system_prompt, user=user_prompt
        )
        return self._parse_response(response, plan.goal)

    def _parse_response(self, response: str, goal: str) -> Plan:
        try:
            # Clean markdown code blocks if present
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            data = json.loads(response.strip())
            steps = [Step(description=s['description'], command=s.get('command', '')) for s in data.get('steps', [])]
            return Plan(steps=steps, goal=goal)
        except Exception as e:
            self.logger.error(f"Failed to parse plan: {e}. Response: {response}")
            # Fallback plan
            return Plan(steps=[Step(description="Manual intervention required: " + goal)], goal=goal)
