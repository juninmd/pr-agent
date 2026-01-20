from pr_agent.git_providers.git_provider import GitProvider
from pr_agent.log import get_logger

class ToolRegistry:
    def __init__(self, git_provider: GitProvider):
        self.git_provider = git_provider
        self.tools = {}

    def register_tool(self, name, description, func):
        self.tools[name] = {
            "description": description,
            "func": func
        }

    def get_tool_definitions(self):
        definitions = []
        for name, info in self.tools.items():
            definitions.append(f"- `{name}`: {info['description']}")
        return "\n".join(definitions)

    async def execute(self, action, args):
        if action in self.tools:
            try:
                get_logger().info(f"Executing tool {action} with args {args}")
                return await self.tools[action]["func"](**args)
            except Exception as e:
                return f"Error executing {action}: {e}"
        return f"Unknown action: {action}"
