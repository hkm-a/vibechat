#!/usr/bin/env bash
# 仅用于 Linux/WSLg 的 Tauri 壳（WebKitGTK）。
# Windows 桌面端应使用 Edge 应用模式（install-windows-shortcut.ps1），
# 不应运行本脚本，因为 WebKit 与 WSLg 的显示效果不同于 Chrome/Edge。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ -f "$HOME/.cargo/env" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.cargo/env"
fi
export PATH="$HOME/.cargo/bin:$PATH"

if ! command -v cargo >/dev/null 2>&1; then
  echo "缺少 Rust。请先安装：https://rustup.rs/"
  exit 1
fi

if [[ ! -d node_modules ]]; then
  npm ci
fi

BIN="$ROOT/src-tauri/target/release/vibechat"
if [[ ! -x "$BIN" ]]; then
  echo "==> 首次执行发布构建，可能需要几分钟"
  npm run build
fi

# 减少常见的 WSLg 图形噪声，仍可能输出少量 MESA 信息。
export WEBKIT_DISABLE_COMPOSITING_MODE="${WEBKIT_DISABLE_COMPOSITING_MODE:-1}"
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"

echo "==> Tauri/WebKit 将连接 http://localhost:6060/"
echo "    页面与浏览器相同，但 WebKit 与 Chrome 的显示效果可能略有差异。"
echo "    Windows 桌面端建议使用 Edge 应用快捷方式。"
exec "$BIN"
