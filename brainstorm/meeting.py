from typing import Awaitable, Callable, Dict, Any, List
from brainstorm.utils import safe_json
from brainstorm.agents.chair import ChairRunner
from brainstorm.agents.specialist import SpecialistRunner

async def run_meeting(
    topic: str,
    constraints: str,
    agenda: List[str],
    chair,
    specialists: List,
    invoke: Callable[[str], Awaitable[str]],
    chair_runner: ChairRunner,
    specialist_runner: SpecialistRunner,
    max_turns: int,
    min_turns: int,
) -> Dict[str, Any]:
    transcript: List[Dict[str, Any]] = []
    proposal = "Ainda não definida. Gerar opções e convergir para uma recomendação final."

    specialist_map = {s.name: s for s in specialists}
    specialist_names = [s.name for s in specialists]

    # começo: o Chair escolhe, mas pode começar no primeiro por simplicidade
    next_speaker = specialist_names[0] if specialist_names else None

    for _ in range(max_turns):
        if not next_speaker:
            break

        # Turno do especialista
        agent = specialist_map[next_speaker]
        sp_prompt = specialist_runner.build_prompt(agent, topic, constraints, agenda, proposal, transcript)
        sp_raw = await invoke(sp_prompt)
        sp_payload = safe_json(sp_raw)
        transcript.append({"speaker": agent.name, "payload": sp_payload})

        upd = sp_payload.get("proposal_update")
        if isinstance(upd, str) and upd.strip():
            proposal = upd.strip()

        # Decisão do Chair
        decide_prompt = chair_runner.build_decide_prompt(
            chair=chair,
            topic=topic,
            constraints=constraints,
            agenda=agenda,
            proposal=proposal,
            transcript=transcript,
            specialists=specialist_names,
            max_turns=max_turns,
            turns_used=len(transcript),
            min_turns=min_turns,
        )
        ch_raw = await invoke(decide_prompt)
        ch_payload = safe_json(ch_raw)
        transcript.append({"speaker": chair.name, "payload": ch_payload})

        # agenda update
        upd_ag = ch_payload.get("agenda_update", [])
        if isinstance(upd_ag, list):
            for item in upd_ag:
                if isinstance(item, str) and item.strip() and item.strip() not in agenda:
                    agenda.append(item.strip())

        # stop rule
        if len(transcript) >= min_turns and bool(ch_payload.get("stop", False)):
            break

        # next speaker (validado)
        ns = ch_payload.get("next_speaker")
        next_speaker = ns if ns in specialist_map else specialist_names[0]

    # ATA final pelo Chair
    minutes_prompt = chair_runner.build_minutes_prompt(chair, topic, constraints, agenda, transcript)
    minutes_raw = await invoke(minutes_prompt)
    minutes = safe_json(minutes_raw)

    return {"turns_used": len(transcript), "transcript": transcript, "final": minutes}
