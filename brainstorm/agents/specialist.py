from typing import List, Dict, Any
from brainstorm.prompt_store import PromptStore
from brainstorm.utils import compact_history

class SpecialistRunner:
    def __init__(self, prompt_store: PromptStore, prompt_path: str):
        self.prompts = prompt_store
        self.prompt_path = prompt_path

    def build_prompt(self, agent, topic: str, constraints: str, agenda: List[str], proposal: str, transcript: List[Dict[str, Any]]) -> str:
        return self.prompts.render(
            self.prompt_path,
            system_instructions=agent.system_instructions,
            name=agent.name,
            specialization=agent.specialization,
            topic=topic,
            constraints=constraints,
            agenda="\n".join([f"- {a}" for a in agenda]),
            proposal=proposal,
            history=compact_history(transcript, last_n=14),
        )
