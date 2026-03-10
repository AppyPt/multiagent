from pathlib import Path
import json
from brainstorm.config import load_config
from brainstorm.prompt_store import PromptStore
from brainstorm.agents.models import ChairAgent, SpecialistAgent
from brainstorm.agents.chair import ChairRunner
from brainstorm.agents.specialist import SpecialistRunner
from brainstorm.meeting import run_meeting

async def run_from_config(config_path: str, invoke):
    cfg = load_config(config_path)

    project_root = str(Path(config_path).resolve().parents[1])  # .../sk_multiagent_brainstorm
    prompts = PromptStore.from_project_root(project_root)

    chair = ChairAgent(name=cfg.chair.name, system_instructions=cfg.chair.system_instructions)
    specialists = [
        SpecialistAgent(
            name=s.name,
            specialization=s.specialization,
            system_instructions=s.system_instructions,
        )
        for s in cfg.specialists
    ]

    chair_runner = ChairRunner(prompts, cfg.prompts.chair_decide, cfg.prompts.chair_minutes)
    specialist_runner = SpecialistRunner(prompts, cfg.prompts.specialist_turn)

    result = await run_meeting(
        topic=cfg.topic,
        constraints=cfg.constraints,
        agenda=cfg.agenda,
        chair=chair,
        specialists=specialists,
        invoke=invoke,
        chair_runner=chair_runner,
        specialist_runner=specialist_runner,
        max_turns=cfg.max_turns,
        min_turns=cfg.min_turns,
    )

    final_text = json.dumps(result["final"], ensure_ascii=False, indent=2)
    return result | {"final_text": final_text}
