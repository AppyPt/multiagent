from __future__ import annotations

import os
from typing import Awaitable, Callable, Optional

from brainstorm.config import DEBUG


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
            "Sugestão (exemplo):\n"
            f"  export {name}='...'\n"
        )
    return val


def make_invoke() -> Callable[[str], Awaitable[str]]:
    """
    Retorna uma função async invoke(prompt)->str.

    Espera as variáveis de ambiente:
      - AZURE_FOUNDRY_OPENAI_BASE_URL  (ex.: https://<recurso>.services.ai.azure.com/openai/v1/)
      - AZURE_FOUNDRY_DEPLOYMENT      (ex.: DeepSeek-V3-0324)
      - AZURE_INFERENCE_CREDENTIAL    (API key)  [ou OPENAI_API_KEY]

    Nota: não coloque a key no código. [[2]]
    """
    base_url = _require("AZURE_FOUNDRY_OPENAI_BASE_URL")
    deployment = _require("AZURE_FOUNDRY_DEPLOYMENT")

    # compat: aceita tanto AZURE_INFERENCE_CREDENTIAL quanto OPENAI_API_KEY
    api_key = _env("AZURE_INFERENCE_CREDENTIAL") or _env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Defina AZURE_INFERENCE_CREDENTIAL (recomendado) ou OPENAI_API_KEY."
        )

    # OpenAI-compatible client (Async)
    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Pacote 'openai' não está instalado no seu ambiente.\n"
            "Instale dentro do seu venv:\n"
            "  python -m pip install -U openai\n"
        ) from e

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def invoke(prompt: str) -> str:
        if DEBUG:
            print("\n[DEBUG prompt]\n", prompt[:2000], "\n")

        resp = await client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        msg = resp.choices[0].message
        # dependendo da versão do SDK, msg pode ser objeto com .content
        content = getattr(msg, "content", None)
        if not content:
            # fallback (caso venha numa estrutura ligeiramente diferente)
            return str(msg)
        return content

    return invoke
