#!/usr/bin/env bash
# 在 WSL 启动 AI NPC：自动从 Windows 用户环境读取 AGNES_API_KEY
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ -z "${AGNES_API_KEY:-}" ]]; then
  if command -v powershell.exe >/dev/null 2>&1; then
    AGNES_API_KEY="$(
      powershell.exe -NoProfile -Command \
        "[Environment]::GetEnvironmentVariable('AGNES_API_KEY','User')" \
        | tr -d '\r' | tail -n1
    )"
    export AGNES_API_KEY
  fi
fi

if [[ -z "${AGNES_API_KEY:-}" || "${AGNES_API_KEY}" == %* ]]; then
  echo "AGNES_API_KEY 未设置。请在 Windows 用户环境变量配置，或 export AGNES_API_KEY=..." >&2
  exit 1
fi

export TINODE_WS="${TINODE_WS:-ws://127.0.0.1:6060/v0/channels}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -U pip
  .venv/bin/pip install -r requirements.txt
fi

# 确保依赖存在
.venv/bin/python -c "import websockets" 2>/dev/null || .venv/bin/pip install -r requirements.txt

exec .venv/bin/python run.py