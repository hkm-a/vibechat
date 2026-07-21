#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
[[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
export PATH="$HOME/.cargo/bin:$PATH"
[[ -d node_modules ]] || npm install
exec npm run dev
