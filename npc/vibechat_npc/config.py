"""配置加载：环境变量优先，WSL 可回读 Windows 用户环境。"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PERSONAS = ROOT / "personas.json"

# 与官方 Tinode 镜像默认 API key 一致
DEFAULT_API_KEY = "AQEAAAABAAD_rAp4DJh05a1HAwFT3A6K"
DEFAULT_WS = "ws://127.0.0.1:6060/v0/channels"
DEFAULT_AGNES_BASE = "https://apihub.agnes-ai.com/v1"
PRIMARY_MODEL = "agnes-2.5-flash"
FALLBACK_MODEL = "agnes-2.0-flash"


@dataclass(frozen=True)
class Persona:
    id: str
    username: str
    password: str
    display_name: str
    system: str


@dataclass(frozen=True)
class Settings:
    tinode_ws: str
    tinode_api_key: str
    agnes_base: str
    agnes_api_key: str
    primary_model: str
    fallback_model: str
    history_limit: int
    max_tokens: int
    temperature: float
    agnes_rpm: int
    group_reply_chance: float
    group_max_replies: int
    personas: tuple[Persona, ...]


def resolve_agnes_api_key() -> str:
    env = os.environ.get("AGNES_API_KEY")
    if env and env.strip() and not env.strip().startswith("%"):
        return env.strip()

    for scope_cmd in (
        "[Environment]::GetEnvironmentVariable('AGNES_API_KEY','User')",
        "[Environment]::GetEnvironmentVariable('AGNES_API_KEY','Machine')",
    ):
        try:
            out = subprocess.check_output(
                ["powershell.exe", "-NoProfile", "-Command", scope_cmd],
                text=True,
                timeout=15,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            continue
        lines = [ln.strip() for ln in out.replace("\r", "").splitlines() if ln.strip()]
        if lines and lines[-1] and not lines[-1].startswith("%"):
            return lines[-1]

    raise SystemExit(
        "未找到 AGNES_API_KEY。\n"
        "请在 Windows 用户环境变量设置 AGNES_API_KEY，或在 WSL 执行：\n"
        "  export AGNES_API_KEY='你的key'"
    )


def load_personas(path: Path | None = None) -> tuple[Persona, ...]:
    p = path or Path(os.environ.get("NPC_PERSONAS", DEFAULT_PERSONAS))
    raw: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    items = []
    for row in raw.get("npcs", []):
        items.append(
            Persona(
                id=row["id"],
                username=row["username"],
                password=row["password"],
                display_name=row.get("display_name") or row["username"],
                system=row["system"],
            )
        )
    if not items:
        raise SystemExit(f"personas 为空: {p}")
    return tuple(items)


def load_settings() -> Settings:
    return Settings(
        tinode_ws=os.environ.get("TINODE_WS", DEFAULT_WS),
        tinode_api_key=os.environ.get("TINODE_API_KEY", DEFAULT_API_KEY),
        agnes_base=os.environ.get("AGNES_BASE_URL", DEFAULT_AGNES_BASE).rstrip("/"),
        agnes_api_key=resolve_agnes_api_key(),
        primary_model=os.environ.get("AGNES_MODEL", PRIMARY_MODEL),
        fallback_model=os.environ.get("AGNES_FALLBACK_MODEL", FALLBACK_MODEL),
        history_limit=int(os.environ.get("NPC_HISTORY_LIMIT", "12")),
        max_tokens=int(os.environ.get("NPC_MAX_TOKENS", "512")),
        temperature=float(os.environ.get("NPC_TEMPERATURE", "0.8")),
        # 全局 Agnes 调用上限（含私聊+群聊）
        agnes_rpm=int(os.environ.get("NPC_AGNES_RPM", "20")),
        # 群聊随机插话概率（每个在线 NPC 独立掷骰，再被 max_replies 截断）
        group_reply_chance=float(os.environ.get("NPC_GROUP_REPLY_CHANCE", "0.12")),
        group_max_replies=int(os.environ.get("NPC_GROUP_MAX_REPLIES", "2")),
        personas=load_personas(),
    )