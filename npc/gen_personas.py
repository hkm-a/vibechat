#!/usr/bin/env python3
"""从花名册重新生成 personas.json。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from vibechat_npc.roster import write_personas_json  # noqa: E402


def main() -> None:
    n = write_personas_json(ROOT / "personas.json")
    print(f"wrote {n} personas -> {ROOT / 'personas.json'}")


if __name__ == "__main__":
    main()