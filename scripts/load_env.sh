#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env.local}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file não encontrado: $ENV_FILE"
  echo "Crie um .env.local (não commitado) com as variáveis."
  exit 1
fi

# Exporta automaticamente todas as variáveis definidas no ficheiro
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "Variáveis carregadas de: $ENV_FILE"
