from dataclasses import dataclass

@dataclass
class Agent:
    name: str
    system_instructions: str

@dataclass
class SpecialistAgent(Agent):
    specialization: str

@dataclass
class ChairAgent(Agent):
    pass
