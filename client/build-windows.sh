#!/usr/bin/env bash
# 从 WSL 调用 Windows Python 打包（源码先同步到 C: 盘，避免 \\wsl$ 访问问题）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
WIN_SRC="/mnt/c/Users/hkm/projects/vibechat-desktop-src"
WIN_SRC_WIN='C:\Users\hkm\projects\vibechat-desktop-src'

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
echo "登录服务器填: localhost:6060 （Docker 端口已映射到 Windows）"