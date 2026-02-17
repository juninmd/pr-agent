from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class State:
    """
    Holds the execution state of the Jules agent.
    Strictly optimized for Clean Code and < 150 LOC.
    """
    task: str
    files: List[str] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)

    def add_history(self, step_description: str, command: str, result: str):
        """Records a step execution."""
        self.history.append({
            "step": step_description,
            "command": command,
            "result": result
        })

    def get_context(self) -> str:
        """Returns a summarized context for the LLM."""
        context = f"Task: {self.task}\nFiles: {', '.join(self.files[:50])}..."
        if self.history:
            last_steps = self.history[-3:] # Keep context short
            context += "\nLast Steps:\n" + "\n".join([f"- {s['step']} -> {s['result'][:100]}..." for s in last_steps])
        return context
