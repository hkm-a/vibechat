#!/usr/bin/env bash
# VibeChat 原生桌面客户端（PySide6，不是浏览器）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -U pip
  .venv/bin/pip install -r requirements.txt
fi

.venv/bin/python -c "import PySide6, websockets" 2>/dev/null || .venv/bin/pip install -r requirements.txt

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
# WSLg / 远程显示
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-}"
exec .venv/bin/python run.py "$@"