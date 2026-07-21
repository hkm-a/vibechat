"""NPC 运行时：收消息 → Agnes → 回消息。"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque

from .agnes import AgnesClient, build_messages
from .budget import GroupReplyCoordinator, SlidingWindowRateLimiter
from .config import Persona, Settings
from .content import content_to_text
from .tinode import TinodeSession

log = logging.getLogger("npc.runtime")


@dataclass
class TopicMemory:
    turns: Deque[tuple[str, str]] = field(default_factory=lambda: deque(maxlen=32))
    last_reply_at: float = 0.0
    busy: bool = False


def _is_group(topic: str) -> bool:
    return str(topic).startswith("grp")


def _is_p2p(topic: str) -> bool:
    return str(topic).startswith("usr")


def _mentioned(text: str, persona: Persona) -> bool:
    t = text.lower()
    names = {
        persona.display_name.strip(),
        persona.username.strip(),
        persona.id.strip(),
    }
    for n in names:
        if not n:
            continue
        if n in text or n.lower() in t:
            return True
        if f"@{n}" in text or f"@{n.lower()}" in t:
            return True
    return False


@dataclass
class NpcAgent:
    persona: Persona
    settings: Settings
    agnes: AgnesClient
    start_gate: asyncio.Semaphore
    rate_limiter: SlidingWindowRateLimiter
    group_coord: GroupReplyCoordinator
    npc_user_ids: set[str]
    memory: dict[str, TopicMemory] = field(default_factory=lambda: defaultdict(TopicMemory))
    session: TinodeSession | None = None

    def _mem(self, topic: str) -> TopicMemory:
        m = self.memory[topic]
        if m.turns.maxlen != self.settings.history_limit * 2:
            m.turns = deque(m.turns, maxlen=max(4, self.settings.history_limit * 2))
        return m

    def _want_group_reply(self, text: str) -> tuple[bool, bool]:
        """返回 (want, mentioned)。群聊：@必回意向；否则随机插话。"""
        mentioned = _mentioned(text, self.persona)
        if mentioned:
            return True, True
        # 随机插话概率（多 NPC 同时掷骰，再由 coordinator 截断）
        if random.random() < self.settings.group_reply_chance:
            return True, False
        return False, False

    async def on_data(self, session: TinodeSession, topic: str, data: dict) -> None:
        text = content_to_text(data.get("content")).strip()
        if not text:
            return
        if not (_is_p2p(topic) or _is_group(topic)):
            return
        if len(text) > 2000:
            text = text[:2000] + "…"

        # 忽略其它 NPC 的群消息连锁风暴：只对「真人」或非 hsr 前缀做随机？
        # 简单策略：群聊里来自任意用户都可触发；靠 RPM + max_replies 控量。
        mem = self._mem(topic)
        if _is_group(topic):
            frm = data.get("from") or "?"
            mem.turns.append(("user", f"[{frm}] {text}"))
        else:
            mem.turns.append(("user", text))

        seq = data.get("seq")
        if isinstance(seq, int):
            try:
                await session.note_read(topic, seq)
            except Exception:  # noqa: BLE001
                pass

        mentioned = False
        if _is_p2p(topic):
            want = True
        elif _is_group(topic):
            # NPC 互刷：只允许被 @ 时接话，随机插话仅针对真人
            frm = data.get("from")
            from_npc = bool(frm and frm in self.npc_user_ids)
            want, mentioned = self._want_group_reply(text)
            if from_npc and not mentioned:
                want = False
        else:
            want = False
        if not want:
            return

        if _is_group(topic):
            claimed = await self.group_coord.try_claim(
                topic=topic,
                seq=seq if isinstance(seq, int) else None,
                text=text,
                persona_id=self.persona.id,
                mentioned=mentioned,
            )
            if not claimed:
                return

        if mem.busy:
            return

        token = time.monotonic()
        mem.last_reply_at = token
        # 群聊随机错峰，更像七嘴八舌
        delay = 0.6 if _is_p2p(topic) else random.uniform(0.8, 3.5)
        await asyncio.sleep(delay)
        if mem.last_reply_at != token:
            return

        # 全局限流：没额度就放弃（群聊随机发言场景）
        if not await self.rate_limiter.acquire_or_skip():
            used, limit = self.rate_limiter.snapshot()
            log.info(
                "[%s] skip reply (rpm %s/%s) topic=%s",
                self.persona.username,
                used,
                limit,
                topic,
            )
            return

        mem.busy = True
        try:
            system = self.persona.system
            if _is_group(topic):
                system = (
                    system
                    + " 你在群聊里，像群友随口插话：短、自然、可接梗；不要复读别人；不要刷屏。"
                )
            messages = build_messages(
                system,
                list(mem.turns),
                history_limit=self.settings.history_limit,
            )
            reply = await asyncio.to_thread(self.agnes.complete, messages)
            reply = (reply or "").strip()
            if not reply:
                reply = "嗯？"
            if len(reply) > 800:
                reply = reply[:800] + "…"
            mem.turns.append(("assistant", reply))
            await session.publish_text(topic, reply)
            used, limit = self.rate_limiter.snapshot()
            log.info(
                "[%s] %s <- %s | rpm %s/%s",
                self.persona.username,
                topic,
                reply[:60].replace("\n", " "),
                used,
                limit,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("[%s] reply failed: %s", self.persona.username, e)
            try:
                await session.publish_text(topic, "（系统：NPC 暂时没接上，稍后再试）")
            except Exception:  # noqa: BLE001
                pass
        finally:
            mem.busy = False

    async def run(self) -> None:
        async with self.start_gate:
            await asyncio.sleep(0.05)

        while True:
            session = TinodeSession(
                ws_url=self.settings.tinode_ws,
                api_key=self.settings.tinode_api_key,
                username=self.persona.username,
                password=self.persona.password,
                on_data=self.on_data,
                ua=f"VibeChat-NPC/{self.persona.id}",
                display_name=self.persona.display_name,
            )
            self.session = session
            try:
                await session.connect_and_login()
                if session.user_id:
                    self.npc_user_ids.add(session.user_id)
                await session.set_display_name(self.persona.display_name)
                log.info("[%s] online as %s", self.persona.username, self.persona.display_name)
                await session.run_forever()
            except Exception as e:  # noqa: BLE001
                log.warning("[%s] disconnected: %s; retry in 5s", self.persona.username, e)
                await asyncio.sleep(5)
            finally:
                await session.close()


async def run_all(settings: Settings) -> None:
    agnes = AgnesClient(
        base_url=settings.agnes_base,
        api_key=settings.agnes_api_key,
        primary_model=settings.primary_model,
        fallback_model=settings.fallback_model,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )
    concurrency = int(os.environ.get("NPC_CONNECT_CONCURRENCY", "12"))
    gate = asyncio.Semaphore(max(1, concurrency))
    rate_limiter = SlidingWindowRateLimiter(rpm=settings.agnes_rpm)
    group_coord = GroupReplyCoordinator(max_replies_per_msg=settings.group_max_replies)
    npc_user_ids: set[str] = set()
    agents = [
        NpcAgent(
            persona=p,
            settings=settings,
            agnes=agnes,
            start_gate=gate,
            rate_limiter=rate_limiter,
            group_coord=group_coord,
            npc_user_ids=npc_user_ids,
        )
        for p in settings.personas
    ]
    log.info(
        "starting %d NPCs | connect=%d rpm=%d group_chance=%.2f group_max=%d | model=%s",
        len(agents),
        concurrency,
        settings.agnes_rpm,
        settings.group_reply_chance,
        settings.group_max_replies,
        settings.primary_model,
    )
    preview = ", ".join(a.persona.display_name for a in agents[:8])
    log.info("roster preview: %s%s", preview, "…" if len(agents) > 8 else "")
    await asyncio.gather(*(a.run() for a in agents))