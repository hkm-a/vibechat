# VibeChat

[![CI](https://github.com/hkm-a/vibechat/actions/workflows/build.yml/badge.svg)](https://github.com/hkm-a/vibechat/actions/workflows/build.yml)
[![Release](https://img.shields.io/github/v/release/hkm-a/vibechat?include_prereleases)](https://github.com/hkm-a/vibechat/releases)
[![License](https://img.shields.io/github/license/hkm-a/vibechat)](LICENSE)
[![Node](https://img.shields.io/badge/node-22-blue)](https://nodejs.org)

Self-hosted instant messaging powered by [Tinode](https://github.com/tinode/chat), with AI NPC bots (Honkai: Star Rail roster).

## Architecture

```
┌─────────────────────────────────────────────────┐
│  always-on (Docker + background processes)      │
│                                                  │
│  MySQL ←── Tinode server ←── WebSocket          │
│                   ↑                              │
│              NPC workers (x80)                   │
│                   ↑                              │
│              Agnes API (LLM)                     │
└─────────────────────────────────────────────────┘
         ↑                    ↑
         │            ┌───────┘
    Web UI           Desktop clients
  (localhost:6060)    (Tauri / Qt / Chrome app)
```

| Layer | Component | Location |
|-------|-----------|----------|
| Database | MySQL 8 | `tinode-mysql` container |
| IM server | Tinode | `tinode-srv` container, port 6060 |
| AI NPC | Python workers | `npc/` — 80 bots, WebSocket to Tinode |
| Web UI | Tinode built-in | http://localhost:6060/ |
| Desktop | Tauri / Qt / Chrome app | `desktop-tauri/` / `client/` |

## Quick start

```bash
# 1. Start the server stack
sudo docker compose up -d

# 2. Start AI NPCs
cd npc && ./start.sh

# 3. Open http://localhost:6060/ and register an account
```

Or use the one-shot launcher:

```bash
./start-desktop.sh
```

## Desktop clients

| Client | UI engine | Notes |
|--------|-----------|-------|
| **Chrome app** (Windows) | Chromium | Same as Web UI. Run `start-on-windows.bat` or desktop shortcut |
| **Tauri** (Linux/WSL) | WebKit | `cd desktop-tauri && ./start.sh` |
| **Qt** (PySide6) | Native | Separate UI, not Web. `cd client && ./start.sh` |

The Web UI and Chrome/Tauri wrappers all render the same HTML/CSS/JS from Tinode. The Qt client is a completely independent implementation.

## Demo accounts

| Account | Password | Persona |
|---------|----------|---------|
| alice | alice123 | March 7th (三月七) |
| bob | bob123 | Firefly (流萤) |
| carol | carol123 | Sparkle (花火) |
| hsr_* | npc123456 | Other HSR characters (auto-registered on NPC start) |

Development email verification code: `123456`

> Register your own account for chatting — the demo accounts are for NPC personas.

## AI NPC

80 playable Honkai: Star Rail characters, each with a unique persona. NPCs connect to Tinode via WebSocket and respond using the Agnes API.

```bash
cd npc && ./start.sh
# Logs: /tmp/vibechat-npc.log
```

- **Private chat**: NPC replies to every message
- **Group chat**: NPC replies when mentioned (@name) or randomly (see config)
- **NPC-to-NPC**: filtered to prevent mutual spam
- **Persona source**: `npc/vibechat_npc/roster.py` → `npc/personas.json`

### Group chat parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `NPC_AGNES_RPM` | 20 | Global Agnes API rate limit (requests/min) |
| `NPC_GROUP_REPLY_CHANCE` | 0.12 | Per-message random reply probability |
| `NPC_GROUP_MAX_REPLIES` | 2 | Max NPC replies per human message |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGNES_API_KEY` | Windows env | Agnes API key |
| `AGNES_MODEL` | `agnes-2.5-flash` | Primary LLM model |
| `AGNES_FALLBACK_MODEL` | `agnes-2.0-flash` | Fallback model |
| `TINODE_WS` | `ws://127.0.0.1:6060/v0/channels` | Tinode WebSocket endpoint |
| `NPC_PERSONAS` | `npc/personas.json` | Persona definitions file |
| `NPC_CONNECT_CONCURRENCY` | 12 | Concurrent WebSocket handshakes |

## Branding

```bash
sudo docker cp tinode-srv:/opt/tinode/static ./branding/static
python3 branding/apply-brand.py
sudo docker compose restart tinode
```

## Reset all data

```bash
sudo docker compose down -v
sudo docker compose up -d
```

## CI / Release

Push a tag to trigger a release build:

```bash
git tag v0.2.0
git push origin v0.2.0
```

The CI pipeline builds installers for Linux (.deb), macOS (.dmg), and Windows (.exe), then publishes them to GitHub Releases.

## License

MIT