#!/usr/bin/env bash
# 一键：起后端(Tinode) + NPC + 打开 Tauri 桌面壳
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> 1/3 启动 Tinode 服务端 (Docker)"
if ! docker info >/dev/null 2>&1; then
  echo "Docker 未运行，尝试: sudo service docker start"
  sudo service docker start || true
  sleep 2
fi
sudo docker compose up -d

echo "==> 2/3 启动 AI NPC（后台）"
if pgrep -f '/home/hkm/projects/teleg/npc/.venv/bin/python run.py' >/dev/null 2>&1 \
  || pgrep -f 'npc/.venv/bin/python run.py' >/dev/null 2>&1; then
  echo "    NPC 已在运行"
else
  (
    cd "$ROOT/npc"
    nohup ./start.sh >>/tmp/vibechat-npc.log 2>&1 &
  )
  echo "    NPC 日志: /tmp/vibechat-npc.log"
fi

echo "==> 3/3 打开桌面客户端 (Tauri 包装 Web)"
echo "    窗口内是 Tinode 网页；服务端仍在 Docker。"
cd "$ROOT/desktop-tauri"
exec ./start.sh