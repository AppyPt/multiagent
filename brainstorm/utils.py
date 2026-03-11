"""
utils.py — Funções utilitárias partilhadas pelo sistema multiagente.

Responsabilidades:
  - Parse seguro de JSON (com fallback para respostas "sujas" do LLM)
  - Formatação de histórico (compacto + resumido)
  - Métricas de transcript (contagem de falas, perguntas abertas, etc.)
  - Fuzzy match de nomes de speaker
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────
# JSON parsing
# ─────────────────────────────────────────────

class JsonParseError(Exception):
    """Erro ao extrair JSON de uma resposta do LLM."""
    pass


def safe_json(text: str) -> Dict[str, Any]:
    """
    Extrai um objecto JSON de uma resposta do LLM.

    Estratégias (por ordem):
      1) Parse directo do texto
      2) Remoção de wrappers ```json ... ``` (markdown code fences)
      3) Extracção do primeiro {...} encontrado no texto

    Raises:
        JsonParseError: se nenhuma estratégia funcionar.
    """
    if not text or not text.strip():
        raise JsonParseError("Resposta vazia do LLM")

    s = text.strip()

    # 1) Tentativa directa
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # 2) Remover code fences (```json ... ``` ou ``` ... ```)
    #    O DeepSeek costuma devolver respostas assim.
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", s, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3) Extrair o primeiro objecto {...} (greedy no último })
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(s[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise JsonParseError(
        f"Não foi possível extrair JSON da resposta ({len(s)} chars): {s[:200]}..."
    )


# ─────────────────────────────────────────────
# Formatação de histórico (transcript)
# ─────────────────────────────────────────────

def _format_turn_full(turn: Dict[str, Any]) -> str:
    """Formata um turno em detalhe completo (JSON)."""
    return f'{turn["speaker"]}: {json.dumps(turn["payload"], ensure_ascii=False)}'


def _format_turn_summary(turn: Dict[str, Any]) -> str:
    """
    Formata um turno de forma resumida (só métricas-chave).
    Poupa tokens nos prompts sem perder informação essencial.
    """
    speaker = turn["speaker"]
    p = turn.get("payload", {})

    # Turno de especialista (tem "maturity")
    if "maturity" in p:
        ideas_n = len(p.get("ideas", []))
        risks_n = len(p.get("risks", []))
        questions_n = len(p.get("questions", []))
        mat = p.get("maturity", "?")
        done = p.get("done", False)
        proposal_snippet = str(p.get("proposal_update", ""))[:100]
        return (
            f"  {speaker}: maturity={mat}, done={done}, "
            f"ideas={ideas_n}, risks={risks_n}, questions={questions_n}, "
            f"proposal='{proposal_snippet}'"
        )

    # Turno de Chair (tem "next_speaker")
    if "next_speaker" in p:
        ns = p.get("next_speaker", "?")
        stop = p.get("stop", False)
        reason_snippet = str(p.get("reason", ""))[:80]
        return f"  {speaker}: next={ns}, stop={stop}, reason='{reason_snippet}'"

    # Fallback genérico
    return f"  {speaker}: {json.dumps(p, ensure_ascii=False)[:150]}"


def compact_history(
    transcript: List[Dict[str, Any]],
    last_n: int = 6,
) -> str:
    """
    Formata o transcript para injecção em prompts.

    - Turnos antigos (antes dos últimos `last_n`) → resumo compacto (1 linha por turno)
    - Turnos recentes (últimos `last_n`) → detalhe completo em JSON

    Isto controla o crescimento do prompt à medida que a reunião avança.
    """
    if not transcript:
        return "(sem histórico ainda)"

    # Se o transcript é pequeno, tudo em detalhe
    if len(transcript) <= last_n:
        return "\n".join(_format_turn_full(t) for t in transcript)

    old = transcript[:-last_n]
    recent = transcript[-last_n:]

    lines: List[str] = []

    # Secção de resumo (turnos antigos)
    lines.append("--- Turnos anteriores (resumo) ---")
    for t in old:
        lines.append(_format_turn_summary(t))

    lines.append("")

    # Secção detalhada (turnos recentes)
    lines.append("--- Turnos recentes (detalhe) ---")
    for t in recent:
        lines.append(_format_turn_full(t))

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Métricas de transcript
# ─────────────────────────────────────────────

def count_speaker_turns(
    transcript: List[Dict[str, Any]],
    chair_name: str,
) -> Dict[str, int]:
    """Conta quantas vezes cada especialista falou (exclui Chair)."""
    counts: Dict[str, int] = {}
    for t in transcript:
        speaker = t["speaker"]
        if speaker != chair_name:
            counts[speaker] = counts.get(speaker, 0) + 1
    return counts


def format_speaker_counts(counts: Dict[str, int]) -> str:
    """Formata contagem de falas para injecção em prompt."""
    if not counts:
        return "(nenhum especialista falou ainda)"
    return ", ".join(f"{name}: {n}x" for name, n in counts.items())


def collect_open_questions(
    transcript: List[Dict[str, Any]],
    chair_name: str,
) -> List[str]:
    """
    Recolhe todas as perguntas feitas por especialistas (campo 'questions').
    Útil para o Chair saber o que ainda está em aberto.
    """
    questions: List[str] = []
    for t in transcript:
        if t["speaker"] == chair_name:
            continue
        payload = t.get("payload", {})
        qs = payload.get("questions", [])
        if isinstance(qs, list):
            questions.extend(q for q in qs if isinstance(q, str) and q.strip())
    return questions


def format_open_questions(questions: List[str], max_show: int = 5) -> str:
    """Formata perguntas abertas para injecção em prompt."""
    if not questions:
        return "(nenhuma)"
    shown = questions[-max_show:]
    suffix = f" (+ {len(questions) - max_show} anteriores)" if len(questions) > max_show else ""
    return "; ".join(shown) + suffix


def last_specialist_metrics(
    transcript: List[Dict[str, Any]],
    chair_name: str,
) -> Dict[str, Any]:
    """Extrai métricas do último turno de especialista."""
    for t in reversed(transcript):
        if t["speaker"] != chair_name:
            p = t.get("payload", {})
            return {
                "name": t["speaker"],
                "maturity": p.get("maturity", 0),
                "done": p.get("done", False),
                "questions_count": len(p.get("questions", [])),
                "ideas_count": len(p.get("ideas", [])),
                "risks_count": len(p.get("risks", [])),
            }
    return {
        "name": "?",
        "maturity": 0,
        "done": False,
        "questions_count": 0,
        "ideas_count": 0,
        "risks_count": 0,
    }


# ─────────────────────────────────────────────
# Fuzzy match de nomes de speaker
# ─────────────────────────────────────────────

def fuzzy_match_speaker(
    name: Optional[str],
    valid_names: List[str],
) -> Optional[str]:
    """
    Resolve um nome (possivelmente truncado/incompleto pelo LLM)
    para um dos nomes válidos de especialista.

    Estratégias:
      1) Match exacto (case-insensitive)
      2) Match parcial (nome contido no válido, ou vice-versa)
    """
    if not name:
        return None

    name_lower = name.strip().lower()

    # 1) Match exacto
    for valid in valid_names:
        if name_lower == valid.lower():
            return valid

    # 2) Match parcial
    for valid in valid_names:
        if name_lower in valid.lower() or valid.lower().startswith(name_lower):
            return valid

    return None


def pick_least_speaking(
    specialist_names: List[str],
    speaker_counts: Dict[str, int],
) -> str:
    """
    Escolhe o agente com MENOS falas (fallback inteligente).
    Em caso de empate, escolhe o primeiro na lista.
    """
    return min(specialist_names, key=lambda n: speaker_counts.get(n, 0))
