#!/usr/bin/env python3
"""启动 VibeChat AI NPC 系统。"""

from __future__ import annotations

import asyncio
import logging
import sys


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # 延迟导入，便于缺依赖时给出提示
    try:
        import websockets  # noqa: F401
    except ImportError:
        print("缺少依赖，请先: pip install -r npc/requirements.txt", file=sys.stderr)
        raise SystemExit(1)

    from vibechat_npc.config import load_settings
    from vibechat_npc.runtime import run_all

    settings = load_settings()
    # 不打印 key
    logging.getLogger("npc").info(
        "tinode=%s agnes=%s personas=%d",
        settings.tinode_ws,
        settings.agnes_base,
        len(settings.personas),
    )
    try:
        asyncio.run(run_all(settings))
    except KeyboardInterrupt:
        print("\nNPC stopped.")


if __name__ == "__main__":
    main()