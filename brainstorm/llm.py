from __future__ import annotations

import os
import time
from typing import Awaitable, Callable, Optional

from brainstorm.config import DEBUG, VERBOSE, log


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name, default)
    if val is not None:
        val = val.strip()
    return val or None


def _require(name: str) -> str:
    val = _env(name)
    if not val:
        raise RuntimeError(
            f"Variável de ambiente obrigatória não definida: {name}\n"
            f"  export {name}='...'\n"
        )
    return val


def make_invoke() -> Callable[[str], Awaitable[str]]:
    base_url   = _require("AZURE_FOUNDRY_OPENAI_BASE_URL")
    deployment = _require("AZURE_FOUNDRY_DEPLOYMENT")

    api_key = _env("AZURE_INFERENCE_CREDENTIAL") or _env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Defina AZURE_INFERENCE_CREDENTIAL ou OPENAI_API_KEY.")

    log(f"LLM configurado: base_url={base_url}")
    log(f"LLM configurado: deployment={deployment}")
    log(f"LLM configurado: api_key={'***' + api_key[-4:]}")

    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError as e:
        raise RuntimeError("Pacote 'openai' não instalado. pip install -U openai") from e

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    call_count = 0

    async def invoke(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        call_id = call_count

        prompt_preview = prompt[:150].replace("\n", " ")
        log(f"[CALL #{call_id}] A enviar pedido ao LLM ({len(prompt)} chars)...")
        if DEBUG:
            print(f"\n[DEBUG PROMPT #{call_id}]\n{prompt[:2000]}\n", flush=True)

        t0 = time.time()

        resp = await client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        elapsed = time.time() - t0

        msg = resp.choices[0].message
        content = getattr(msg, "content", None)
        if not content:
            content = str(msg)

        content_preview = content[:200].replace("\n", " ")
        log(f"[CALL #{call_id}] Resposta recebida em {elapsed:.1f}s ({len(content)} chars): {content_preview}...")

        return content

    return invoke
