#!/usr/bin/env bash
# 从 WSL 调用 Windows Python 打包（源码先同步到 C: 盘，避免 \\wsl$ 访问问题）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
WIN_SRC_WIN="$(
  powershell.exe -NoProfile -Command \
    '[IO.Path]::Combine($env:TEMP, "vibechat-qt-build-source")' \
    | tr -d '\r' | tail -n1
)"
WIN_SRC="$(wslpath -u "$WIN_SRC_WIN")"

case "$WIN_SRC" in
  /mnt/?/*/vibechat-qt-build-source) ;;
  *)
    echo "拒绝使用未验证的 Windows 暂存目录：$WIN_SRC" >&2
    exit 1
    ;;
esac

echo "==> 同步源码到 Windows 路径: $WIN_SRC"
mkdir -p "$WIN_SRC"
rsync -a --delete \
  --exclude '.venv' \
  --exclude '.venv-win' \
  --exclude '__pycache__' \
  --exclude 'build' \
  --exclude 'dist' \
  --exclude '*.pyc' \
  "$ROOT/" "$WIN_SRC/"

echo "==> 在 Windows 上执行 build-windows.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$WIN_SRC_WIN\build-windows.ps1"

echo ""
echo "Windows 桌面应出现 VibeChat 快捷方式。"
echo "登录服务器填写：localhost:6060（Docker 端口已映射到 Windows）"
