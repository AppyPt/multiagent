import os
from openai import OpenAI

# Foundry resource endpoint (OpenAI-compatible) [[9]]
endpoint = "https://deliveryaihub7596701848.services.ai.azure.com/openai/v1/"
deployment_name = "DeepSeek-V3-0324"  # nome do deployment no Foundry [[1]]

api_key = "colocar aqui a chave do foundry"

client = OpenAI(
    base_url=endpoint,
    api_key=api_key,
)

resp = client.chat.completions.create(
    model=deployment_name,
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say only: ok + the result of 2+2."},
    ],
    temperature=0,
)

print(resp.choices[0].message.content)
