#!/usr/bin/env bash
# WSL-only Tauri shell (WebKitGTK). For Linux/WSLg development.
# Windows desktop should use Edge --app (install-windows-shortcut.ps1),
# NOT this script — WebKit + WSLg looks different from Chrome/Edge.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ -f "$HOME/.cargo/env" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.cargo/env"
fi
export PATH="$HOME/.cargo/bin:$PATH"

if ! command -v cargo >/dev/null 2>&1; then
  echo "Rust missing. Install: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
  exit 1
fi

mkdir -p dist
cp -f index.html dist/index.html

if [[ ! -d node_modules ]]; then
  npm install
fi

BIN="$ROOT/src-tauri/target/release/vibechat"
if [[ ! -x "$BIN" ]]; then
  echo "==> first release build (few minutes)"
  npm run build
fi

# Soften common WSLg noise (still may print some MESA lines)
export WEBKIT_DISABLE_COMPOSITING_MODE="${WEBKIT_DISABLE_COMPOSITING_MODE:-1}"
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"

echo "==> Tauri/WebKit -> http://localhost:6060/"
echo "    Same HTML as browser; engine is WebKit (not Chrome), so look can differ slightly."
echo "    On Windows desktop prefer Edge app shortcut (identical Blink engine)."
exec "$BIN"