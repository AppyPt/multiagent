import os
from openai import OpenAI

# Espera estas variáveis de ambiente (exemplos abaixo):
# - AZURE_FOUNDRY_OPENAI_BASE_URL  -> "https://deliveryaihub7596701848.services.ai.azure.com/openai/v1/"
# - AZURE_FOUNDRY_DEPLOYMENT       -> "DeepSeek-V3-0324"
# - AZURE_INFERENCE_CREDENTIAL     -> "<sua_key>"  (ou AZURE_OPENAI_API_KEY)

endpoint = os.getenv("AZURE_FOUNDRY_OPENAI_BASE_URL")
deployment_name = os.getenv("AZURE_FOUNDRY_DEPLOYMENT")
api_key = os.getenv("AZURE_INFERENCE_CREDENTIAL") or os.getenv("AZURE_OPENAI_API_KEY")

if not endpoint:
    raise RuntimeError("Falta AZURE_FOUNDRY_OPENAI_BASE_URL (ex.: https://<resource>.services.ai.azure.com/openai/v1/ )")
if not deployment_name:
    raise RuntimeError("Falta AZURE_FOUNDRY_DEPLOYMENT (ex.: DeepSeek-V3-0324)")
if not api_key:
    raise RuntimeError("Falta AZURE_INFERENCE_CREDENTIAL (recomendado) ou AZURE_OPENAI_API_KEY")  # exemplo env via os.getenv [[9]]

client = OpenAI(
    base_url=endpoint,   # Foundry endpoint OpenAI-compatible /openai/v1 [[6]]
    api_key=api_key,
)

resp = client.chat.completions.create(
    model=deployment_name,  # deployment name no Foundry [[5]]
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say only: ok + the result of 2+2."},
    ],
    temperature=0,
)

print(resp.choices[0].message.content)
