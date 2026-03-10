import json
from typing import Dict, Any, List

def safe_json(text: str) -> Dict[str, Any]:
    s = text.strip()
    try:
        return json.loads(s)
    except Exception:
        a = s.find("{")
        b = s.rfind("}")
        if a != -1 and b != -1 and b > a:
            return json.loads(s[a:b+1])
        raise

def compact_history(transcript: List[Dict[str, Any]], last_n: int = 12) -> str:
    chunk = transcript[-last_n:]
    lines = []
    for t in chunk:
        lines.append(f'{t["speaker"]}: {json.dumps(t["payload"], ensure_ascii=False)}')
    return "\n".join(lines) if lines else "(sem histórico ainda)"
