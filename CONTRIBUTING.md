# Contributing

## Project structure

```
├── docker-compose.yml      # Tinode + MySQL stack
├── branding/                # Web UI brand overlay
├── npc/                     # AI NPC workers (Python)
├── client/                  # PySide6 Qt client
├── desktop-tauri/           # Tauri desktop wrapper
└── .github/workflows/       # CI / release
```

## Development workflow

1. Start the stack: `sudo docker compose up -d`
2. Start NPC: `cd npc && ./start.sh`
3. Open http://localhost:6060/ or run a desktop client

## Code style

- **Python** — keep it simple; no type annotations required for short scripts
- **Shell** — `set -euo pipefail` at the top of every script
- **CI** — prefer `actions/upload-artifact@v4` over inline binary uploads
- **Branding** — edit `branding/static/`, then `apply-brand.py` and restart tinode

## Pull requests

- Keep PRs focused on a single concern
- Update the README if you change the startup flow or add a dependency
- Make sure `docker compose up -d` still works after your changes

## NPC personas

Personas live in `npc/vibechat_npc/roster.py`. To regenerate:

```bash
cd npc
python3 gen_personas.py
```

Then restart the NPC process.