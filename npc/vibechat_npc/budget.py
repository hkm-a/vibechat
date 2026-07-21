"""全局限流与群聊抢答协调。"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field

log = logging.getLogger("npc.budget")


@dataclass
class SlidingWindowRateLimiter:
    """滑动窗口 RPM 限流（全进程共享）。"""

    rpm: int = 20
    window_sec: float = 60.0
    _ts: deque[float] = field(default_factory=deque)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def try_acquire(self) -> bool:
        now = time.monotonic()
        async with self._lock:
            while self._ts and now - self._ts[0] >= self.window_sec:
                self._ts.popleft()
            if len(self._ts) >= max(1, self.rpm):
                return False
            self._ts.append(now)
            return True

    async def acquire_or_skip(self) -> bool:
        ok = await self.try_acquire()
        if not ok:
            log.debug("rate limit hit rpm=%s", self.rpm)
        return ok

    def snapshot(self) -> tuple[int, int]:
        now = time.monotonic()
        while self._ts and now - self._ts[0] >= self.window_sec:
            self._ts.popleft()
        return len(self._ts), self.rpm


@dataclass
class GroupReplyCoordinator:
    """同一条群消息最多 N 个 NPC 抢答，避免齐刷。"""

    max_replies_per_msg: int = 2
    _claims: dict[str, list[str]] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _last_gc: float = 0.0

    def _key(self, topic: str, seq: int | None, text: str) -> str:
        if seq is not None:
            return f"{topic}#{seq}"
        return f"{topic}#{hash(text) & 0xFFFFFFFF}"

    async def try_claim(
        self,
        *,
        topic: str,
        seq: int | None,
        text: str,
        persona_id: str,
        mentioned: bool,
    ) -> bool:
        key = self._key(topic, seq, text)
        async with self._lock:
            now = time.monotonic()
            if now - self._last_gc > 120:
                # 粗暴 GC，防止无限涨
                if len(self._claims) > 500:
                    self._claims.clear()
                self._last_gc = now

            claimed = self._claims.setdefault(key, [])
            if persona_id in claimed:
                return False
            # @点名：额外挤进 1 个名额
            limit = self.max_replies_per_msg + (1 if mentioned else 0)
            if len(claimed) >= max(1, limit):
                return False
            claimed.append(persona_id)
            return True