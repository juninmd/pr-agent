from jinja2 import Template
from pr_agent.config_loader import get_settings

class PromptGenerator:
    def __init__(self, tool_definitions):
        self.tool_definitions = tool_definitions

    def build_system_prompt(self):
        prompt = get_settings().pr_code_agent.system_prompt
        return Template(prompt).render(tools=self.tool_definitions)

    def build_user_prompt(self, task, history):
        prompt = get_settings().pr_code_agent.user_prompt
        return Template(prompt).render(task=task, history=history)
