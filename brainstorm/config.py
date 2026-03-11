from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any
import tomllib
import os

DEBUG   = os.getenv("DEBUG",   "0") == "1"
VERBOSE = os.getenv("VERBOSE", "1") == "1"   # ligado por defeito enquanto develops

def log(msg: str) -> None:
    """Logger simples controlado por VERBOSE."""
    if VERBOSE:
        print(f"[LOG] {msg}", flush=True)

@dataclass
class SpecialistProfile:
    name: str
    specialization: str
    system_instructions: str
    priority: int = 0

@dataclass
class ChairProfile:
    name: str
    system_instructions: str

@dataclass
class PromptPaths:
    chair_decide: str
    chair_minutes: str
    specialist_turn: str

@dataclass
class MeetingConfig:
    topic: str
    constraints: str
    agenda: List[str]
    max_turns: int
    min_turns: int
    max_specialists: int
    prompts: PromptPaths
    chair: ChairProfile
    specialists: List[SpecialistProfile]

def load_config(path: str) -> MeetingConfig:
    p = Path(path)
    log(f"A carregar config de: {p.resolve()}")

    data = tomllib.loads(p.read_text(encoding="utf-8"))

    meeting = data["meeting"]
    prompts = data["prompts"]
    chair = data["chair"]
    specialists = data.get("specialists", [])

    spec_profiles = [
        SpecialistProfile(
            name=s["name"],
            specialization=s["specialization"],
            system_instructions=s["system_instructions"],
            priority=int(s.get("priority", 0)),
        )
        for s in specialists
    ]

    spec_profiles.sort(key=lambda x: x.priority, reverse=True)
    max_specs = int(meeting.get("max_specialists", len(spec_profiles)))
    spec_profiles = spec_profiles[:max_specs]

    log(f"Config carregada: topic='{meeting['topic'][:60]}...', max_turns={meeting['max_turns']}, specialists={[s.name for s in spec_profiles]}")

    return MeetingConfig(
        topic=meeting["topic"],
        constraints=meeting["constraints"],
        agenda=list(meeting["agenda"]),
        max_turns=int(meeting["max_turns"]),
        min_turns=int(meeting["min_turns"]),
        max_specialists=max_specs,
        prompts=PromptPaths(
            chair_decide=prompts["chair_decide"],
            chair_minutes=prompts["chair_minutes"],
            specialist_turn=prompts["specialist_turn"],
        ),
        chair=ChairProfile(
            name=chair["name"],
            system_instructions=chair["system_instructions"],
        ),
        specialists=spec_profiles,
    )
