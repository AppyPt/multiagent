"""
meeting.py — Orquestração da reunião multiagente (brainstorm).

Fixes aplicados vs. versão anterior:
  FIX #1 — Contagem separada de turnos de especialistas vs. entradas totais no transcript
  FIX #2 — Métricas concretas injetadas no prompt do Chair (speaker_counts, open_questions, last maturity)
  FIX #3 — Fuzzy match para nomes de speaker devolvidos pelo Chair (ex.: "Agente" → "Agente B (Crítica)")
  FIX #4 — Fallback inteligente: escolhe o agente com MENOS falas (em vez de sempre o primeiro)
  FIX #5 — Stop rule baseada em specialist_turns (não em len(transcript) que mistura Chair)
  FIX #6 — Histórico resumido para turnos antigos (controlo de tamanho de prompt)
"""

from __future__ import annotations

import json
from typing import Awaitable, Callable, Dict, Any, List

from brainstorm.utils import (
    safe_json,
    count_speaker_turns,
    format_speaker_counts,
    collect_open_questions,
    format_open_questions,
    last_specialist_metrics,
    fuzzy_match_speaker,
    pick_least_speaking,
)

from brainstorm.config import log
from brainstorm.agents.chair import ChairRunner
from brainstorm.agents.specialist import SpecialistRunner


# ─────────────────────────────────────────────
# Funções auxiliares de métricas
# ─────────────────────────────────────────────

def _count_speaker_turns(
    transcript: List[Dict[str, Any]], chair_name: str
) -> Dict[str, int]:
    """Conta quantas vezes cada especialista falou (exclui Chair)."""  # FIX #1
    counts: Dict[str, int] = {}
    for t in transcript:
        speaker = t["speaker"]
        if speaker != chair_name:
            counts[speaker] = counts.get(speaker, 0) + 1
    return counts


def _collect_open_questions(
    transcript: List[Dict[str, Any]], chair_name: str
) -> List[str]:
    """Recolhe perguntas feitas por especialistas (campo 'questions')."""  # FIX #2
    questions: List[str] = []
    for t in transcript:
        if t["speaker"] == chair_name:
            continue
        payload = t.get("payload", {})
        qs = payload.get("questions", [])
        if isinstance(qs, list):
            questions.extend(q for q in qs if isinstance(q, str) and q.strip())
    return questions


def _last_specialist_metrics(
    transcript: List[Dict[str, Any]], chair_name: str
) -> Dict[str, Any]:
    """Extrai maturity/done/questions do último turno de especialista."""  # FIX #2
    for t in reversed(transcript):
        if t["speaker"] != chair_name:
            p = t.get("payload", {})
            return {
                "name": t["speaker"],
                "maturity": p.get("maturity", 0),
                "done": p.get("done", False),
                "questions_count": len(p.get("questions", [])),
            }
    return {"name": "?", "maturity": 0, "done": False, "questions_count": 0}


def _fuzzy_match_speaker(
    name: str | None, valid_names: List[str]
) -> str | None:
    """
    Tenta resolver um nome (possivelmente truncado ou incompleto)
    para um dos nomes válidos de especialista.
    """  # FIX #3
    if not name:
        return None
    name_lower = name.strip().lower()
    # match exato
    for valid in valid_names:
        if name_lower == valid.lower():
            return valid
    # match parcial (o nome devolvido está contido no nome válido, ou vice-versa)
    for valid in valid_names:
        if name_lower in valid.lower() or valid.lower().startswith(name_lower):
            return valid
    return None


def _pick_least_speaking(
    specialist_names: List[str], speaker_counts: Dict[str, int]
) -> str:
    """Escolhe o agente que falou MENOS vezes (fallback inteligente)."""  # FIX #4
    return min(specialist_names, key=lambda n: speaker_counts.get(n, 0))


def _summarize_history(
    transcript: List[Dict[str, Any]], recent_n: int = 6
) -> str:
    """
    Turnos antigos → resumo compacto (speaker + métricas-chave).
    Turnos recentes → detalhe completo em JSON.
    Isto evita que o prompt cresça linearmente com o número de turnos.
    """  # FIX #6
    if len(transcript) <= recent_n:
        lines = []
        for t in transcript:
            lines.append(f'{t["speaker"]}: {json.dumps(t["payload"], ensure_ascii=False)}')
        return "\n".join(lines) if lines else "(sem histórico ainda)"

    old = transcript[:-recent_n]
    recent = transcript[-recent_n:]

    old_lines = ["--- Turnos anteriores (resumo) ---"]
    for t in old:
        speaker = t["speaker"]
        p = t.get("payload", {})
        if "maturity" in p:
            # Specialist turn
            ideas_n = len(p.get("ideas", []))
            risks_n = len(p.get("risks", []))
            mat = p.get("maturity", "?")
            done = p.get("done", False)
            proposal_snippet = str(p.get("proposal_update", ""))[:80]
            old_lines.append(
                f"  {speaker}: maturity={mat}, done={done}, "
                f"ideas={ideas_n}, risks={risks_n}, proposal='{proposal_snippet}...'"
            )
        elif "next_speaker" in p:
            # Chair decision
            ns = p.get("next_speaker", "?")
            stop = p.get("stop", False)
            reason_snippet = str(p.get("reason", ""))[:60]
            old_lines.append(f"  {speaker}: next={ns}, stop={stop}, reason='{reason_snippet}'")
        else:
            old_lines.append(f"  {speaker}: {json.dumps(p, ensure_ascii=False)[:120]}")

    old_lines.append("")
    old_lines.append("--- Turnos recentes (detalhe completo) ---")

    for t in recent:
        old_lines.append(f'{t["speaker"]}: {json.dumps(t["payload"], ensure_ascii=False)}')

    return "\n".join(old_lines)


# ─────────────────────────────────────────────
# Orquestração principal
# ─────────────────────────────────────────────

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
    """
    Corre a reunião de brainstorming.

    Args:
        max_turns: número máximo de turnos DE ESPECIALISTAS (não conta decisões do Chair).  # FIX #1
        min_turns: turnos mínimos de especialistas antes de permitir STOP.
    """
    transcript: List[Dict[str, Any]] = []
    proposal = "Ainda não definida. Gerar opções e convergir para uma recomendação final."

    specialist_map = {s.name: s for s in specialists}
    specialist_names = [s.name for s in specialists]

    next_speaker = specialist_names[0] if specialist_names else None

    specialist_turns_done = 0  # FIX #1 — conta SÓ turnos de especialistas

    log(f"Reunião: max_turns={max_turns} (specialist), min_turns={min_turns}")
    log(f"Especialistas: {specialist_names}")
    log(f"Primeiro orador: {next_speaker}")
    log("-" * 60)

    while specialist_turns_done < max_turns:
        if not next_speaker:
            log("Sem próximo orador. A terminar.")
            break

        specialist_turns_done += 1  # FIX #1

        # ──── Turno do especialista ────
        log(f"")
        log(f"══ TURNO {specialist_turns_done}/{max_turns} (specialist) ══ Orador: {next_speaker}")

        agent = specialist_map[next_speaker]
        sp_prompt = specialist_runner.build_prompt(
            agent, topic, constraints, agenda, proposal, transcript
        )

        log(f"   A chamar LLM para {next_speaker} ({len(sp_prompt)} chars)...")
        sp_raw = await invoke(sp_prompt)

        try:
            sp_payload = safe_json(sp_raw)
        except Exception as e:
            log(f"   ERRO parse JSON de {next_speaker}: {e}")
            log(f"   Raw: {sp_raw[:500]}")
            sp_payload = {
                "ideas": [], "risks": [], "questions": [],
                "proposal_update": "", "maturity": 0, "done": False,
            }

        transcript.append({"speaker": agent.name, "payload": sp_payload})

        # ── Log métricas do especialista ──
        maturity = sp_payload.get("maturity", "?")
        done = sp_payload.get("done", False)
        ideas_count = len(sp_payload.get("ideas", []))
        risks_count = len(sp_payload.get("risks", []))
        questions_list = sp_payload.get("questions", [])
        log(
            f"   {next_speaker}: maturity={maturity}, done={done}, "
            f"ideas={ideas_count}, risks={risks_count}, questions={len(questions_list)}"
        )

        upd = sp_payload.get("proposal_update")
        if isinstance(upd, str) and upd.strip():
            proposal = upd.strip()
            log(f"   Proposta atualizada: {proposal[:120]}...")

        # ──── Calcular métricas para o Chair ────  # FIX #2
        speaker_counts = _count_speaker_turns(transcript, chair.name)
        open_questions = _collect_open_questions(transcript, chair.name)
        last_metrics = _last_specialist_metrics(transcript, chair.name)

        speaker_counts_str = ", ".join(f"{k}: {v}x" for k, v in speaker_counts.items())
        open_questions_str = (
            "; ".join(open_questions[-5:]) if open_questions else "(nenhuma)"
        )

        log(f"   Métricas → falas: [{speaker_counts_str}]")
        log(f"   Métricas → perguntas abertas: {len(open_questions)}")

        # ──── Decisão do Chair ────
        log(f"   A consultar Chair...")

        decide_prompt = chair_runner.build_decide_prompt(
            chair=chair,
            topic=topic,
            constraints=constraints,
            agenda=agenda,
            proposal=proposal,
            transcript=transcript,
            specialists=specialist_names,
            max_turns=max_turns,
            turns_used=specialist_turns_done,  # FIX #1 — só specialist turns
            min_turns=min_turns,
            # ── Métricas extra (FIX #2) ──
            speaker_counts=speaker_counts_str,
            open_questions=open_questions_str,
            open_questions_count=str(len(open_questions)),
            last_speaker_name=last_metrics["name"],
            last_speaker_maturity=str(last_metrics["maturity"]),
            last_speaker_done=str(last_metrics["done"]),
        )

        ch_raw = await invoke(decide_prompt)

        try:
            ch_payload = safe_json(ch_raw)
        except Exception as e:
            log(f"   ERRO parse JSON do Chair: {e}")
            log(f"   Raw: {ch_raw[:500]}")
            ch_payload = {
                "next_speaker": specialist_names[0],
                "reason": "fallback (parse error)",
                "stop": False,
                "agenda_update": [],
            }

        transcript.append({"speaker": chair.name, "payload": ch_payload})

        chair_next = ch_payload.get("next_speaker", "?")
        chair_stop = ch_payload.get("stop", False)
        chair_reason = ch_payload.get("reason", "")
        log(f"   Chair: next='{chair_next}', stop={chair_stop}, reason='{chair_reason[:80]}'")

        # ── Agenda update ──
        upd_ag = ch_payload.get("agenda_update", [])
        if isinstance(upd_ag, list):
            for item in upd_ag:
                if isinstance(item, str) and item.strip() and item.strip() not in agenda:
                    agenda.append(item.strip())
                    log(f"   Agenda +: {item.strip()}")

        # ── Stop rule (baseada em specialist_turns) ──  # FIX #5
        if specialist_turns_done >= min_turns and bool(ch_payload.get("stop", False)):
            log(
                f"   Chair pediu STOP após {specialist_turns_done} specialist turns "
                f"(min={min_turns}). A encerrar."
            )
            break

        # ── Next speaker (com fuzzy match + fallback inteligente) ──  # FIX #3 + #4
        ns = ch_payload.get("next_speaker")
        matched = _fuzzy_match_speaker(ns, specialist_names)

        if matched:
            next_speaker = matched
            if matched != ns:
                log(f"   Fuzzy match: '{ns}' → '{matched}'")
        else:
            fallback = _pick_least_speaking(specialist_names, speaker_counts)
            log(
                f"   AVISO: Chair indicou '{ns}' (inválido). "
                f"Fallback → '{fallback}' (menos falas: {speaker_counts.get(fallback, 0)}x)"
            )
            next_speaker = fallback

    # ──── ATA final ────
    log("")
    log("═" * 60)
    log(f"A gerar ATA (Chair)... specialist_turns={specialist_turns_done}")

    minutes_prompt = chair_runner.build_minutes_prompt(
        chair, topic, constraints, agenda, transcript
    )
    minutes_raw = await invoke(minutes_prompt)

    try:
        minutes = safe_json(minutes_raw)
    except Exception as e:
        log(f"ERRO parse ATA: {e}")
        minutes = {
            "final_solution": "ERRO ao gerar ATA",
            "rationale": [],
            "tradeoffs": [],
            "action_items": [],
        }

    log(f"ATA gerada. specialist_turns={specialist_turns_done}, transcript_entries={len(transcript)}")
    log("═" * 60)

    return {
        "specialist_turns": specialist_turns_done,
        "turns_used": len(transcript),
        "transcript": transcript,
        "final": minutes,
    }
