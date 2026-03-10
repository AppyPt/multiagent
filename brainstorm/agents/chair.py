from typing import List, Dict, Any
from brainstorm.prompt_store import PromptStore
from brainstorm.utils import compact_history

class ChairRunner:
    def __init__(self, prompt_store: PromptStore, decide_path: str, minutes_path: str):
        self.prompts = prompt_store
        self.decide_path = decide_path
        self.minutes_path = minutes_path

    def build_decide_prompt(self, chair, topic, constraints, agenda, proposal, transcript, specialists, max_turns, turns_used, min_turns) -> str:
        return self.prompts.render(
            self.decide_path,
            system_instructions=chair.system_instructions,
            topic=topic,
            constraints=constraints,
            agenda="\n".join([f"- {a}" for a in agenda]),
            proposal=proposal,
            history=compact_history(transcript, last_n=14),
            specialists=", ".join(specialists),
            max_turns=str(max_turns),
            turns_used=str(turns_used),
            min_turns=str(min_turns),
        )

    def build_minutes_prompt(self, chair, topic, constraints, agenda, transcript) -> str:
        return self.prompts.render(
            self.minutes_path,
            system_instructions=chair.system_instructions,
            topic=topic,
            constraints=constraints,
            agenda="\n".join([f"- {a}" for a in agenda]),
            history=compact_history(transcript, last_n=60),
        )
