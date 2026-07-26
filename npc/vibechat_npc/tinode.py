"""Tinode JSON WebSocket 最小客户端（单用户会话）。"""

from __future__ import annotations

import asyncio
import base64
import itertools
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

log = logging.getLogger("npc.tinode")

OnData = Callable[["TinodeSession", str, dict[str, Any]], Awaitable[None]]


def basic_secret(username: str, password: str) -> str:
    return base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")


async def _ws_connect(url: str):
    try:
        from websockets.asyncio.client import connect as ws_connect
    except ImportError:  # websockets < 13
        from websockets import connect as ws_connect  # type: ignore
    return await ws_connect(
        url,
        open_timeout=20,
        max_size=4 * 1024 * 1024,
        ping_interval=20,
        ping_timeout=20,
    )


@dataclass
class TinodeSession:
    ws_url: str
    api_key: str
    username: str
    password: str
    on_data: OnData
    ua: str = "VibeChat-NPC/0.1"
    display_name: str | None = None
    # 只处理连接之后的新消息
    ready_at: float = field(default=0.0)
    _ws: Any = field(default=None, repr=False)
    _id_seq: Any = field(default_factory=lambda: itertools.count(1))
    _pending: dict[str, asyncio.Future] = field(default_factory=dict, repr=False)
    _reader_task: asyncio.Task | None = field(default=None, repr=False)
    user_id: str | None = None
    _subscribed: set[str] = field(default_factory=set)
    _sub_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _closed: asyncio.Event = field(default_factory=asyncio.Event)

    def _next_id(self) -> str:
        return str(next(self._id_seq))

    async def send(self, pkt: dict[str, Any], *, wait: bool = False, timeout: float = 20.0) -> Any:
        assert self._ws is not None
        wait_id: str | None = None
        for key, body in list(pkt.items()):
            if isinstance(body, dict) and "id" not in body:
                body = {**body, "id": self._next_id()}
                pkt[key] = body
            if wait and isinstance(body, dict) and "id" in body:
                wait_id = str(body["id"])

        fut: asyncio.Future | None = None
        if wait and wait_id:
            fut = asyncio.get_running_loop().create_future()
            self._pending[wait_id] = fut

        await self._ws.send(json.dumps(pkt, ensure_ascii=False))
        if not fut:
            return None
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            if wait_id:
                self._pending.pop(wait_id, None)

    async def connect_and_login(self) -> None:
        url = self.ws_url
        sep = "&" if "?" in url else "?"
        if "apikey=" not in url:
            url = f"{url}{sep}apikey={self.api_key}"
        log.info("[%s] 正在连接 %s", self.username, url.split("?")[0])
        self._ws = await _ws_connect(url)
        self._reader_task = asyncio.create_task(
            self._reader_loop(), name=f"tinode-reader-{self.username}"
        )

        ctrl = await self.send(
            {"hi": {"ver": "0.22", "ua": self.ua, "lang": "zh-CN"}},
            wait=True,
        )
        log.info("[%s] 握手响应：%s", self.username, (ctrl or {}).get("text"))

        login = await self.send(
            {
                "login": {
                    "scheme": "basic",
                    "secret": basic_secret(self.username, self.password),
                }
            },
            wait=True,
        )
        code = (login or {}).get("code", 500)
        if code >= 400:
            # 账号不存在 → 自动注册
            if code in (401, 404, 409) or "auth" in str(login).lower() or "not found" in str(login).lower():
                await self._register_account()
                login = await self.send(
                    {
                        "login": {
                            "scheme": "basic",
                            "secret": basic_secret(self.username, self.password),
                        }
                    },
                    wait=True,
                )
                code = (login or {}).get("code", 500)
            if code >= 400:
                raise RuntimeError(f"{self.username} 登录失败：{login}")

        params = login.get("params") or {}
        self.user_id = params.get("user")
        log.info("[%s] 已登录为 %s", self.username, self.user_id)

        # 只拉订阅列表，不拉历史 data
        me_meta = await self.send(
            {"sub": {"topic": "me", "get": {"what": "sub desc"}}},
            wait=True,
        )
        if me_meta and me_meta.get("code", 500) >= 400:
            raise RuntimeError(f"订阅 me 失败：{me_meta}")
        self._subscribed.add("me")
        self.ready_at = time.time()

    async def _register_account(self) -> None:
        """用 basic 方案创建账号；若已存在则忽略。"""
        fn = (self.display_name or self.username).strip()
        # 同步 tags，便于 fnd 按 alias、用户名或角色名搜索。
        tags = [self.username, f"alias:{self.username}"]
        if self.display_name:
            tags.append(self.display_name)
        acc = await self.send(
            {
                "acc": {
                    "user": "new",
                    "scheme": "basic",
                    "secret": basic_secret(self.username, self.password),
                    "login": False,
                    "desc": {
                        "public": {"fn": fn},
                        "tags": tags,
                    },
                }
            },
            wait=True,
            timeout=30.0,
        )
        code = (acc or {}).get("code", 500)
        # 409 表示账号已存在，200 表示创建成功。
        if code >= 400 and code != 409:
            # 有的部署返回 200 + params；有的 409
            log.warning("[%s] 注册响应：%s", self.username, acc)
            if code >= 500:
                raise RuntimeError(f"{self.username} 注册失败：{acc}")
        else:
            log.info("[%s] 已注册为 %s", self.username, fn)

    async def set_display_name(self, display_name: str) -> None:
        """更新 me 的公开显示名（联系人列表可见）。"""
        name = (display_name or "").strip()
        if not name:
            return
        self.display_name = name
        ctrl = await self.send(
            {
                "set": {
                    "topic": "me",
                    "desc": {
                        "public": {"fn": name},
                        # 同步 tags，便于搜索
                        "tags": [self.username, f"alias:{self.username}", name],
                    },
                }
            },
            wait=True,
            timeout=15.0,
        )
        code = (ctrl or {}).get("code", 500)
        if code >= 400:
            # tags 可能因权限失败，降级只改 fn
            ctrl = await self.send(
                {"set": {"topic": "me", "desc": {"public": {"fn": name}}}},
                wait=True,
                timeout=15.0,
            )
            code = (ctrl or {}).get("code", 500)
        if code >= 400:
            log.warning("[%s] 设置显示名称失败：%s", self.username, ctrl)
        else:
            log.info("[%s] 显示名称已更新为 %s", self.username, name)

    async def subscribe_topic(self, topic: str) -> None:
        if not topic or topic in self._subscribed:
            return
        async with self._sub_lock:
            if topic in self._subscribed:
                return
            ctrl = await self.send(
                {"sub": {"topic": topic, "get": {"what": "desc sub"}}},
                wait=True,
                timeout=20.0,
            )
            code = (ctrl or {}).get("code", 500)
            if code >= 400 and code != 304:
                log.warning("[%s] 订阅 %s 失败：%s", self.username, topic, ctrl)
                return
            self._subscribed.add(topic)
            log.info("[%s] 已订阅 %s", self.username, topic)

    async def publish_text(self, topic: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        await self.send(
            {
                "pub": {
                    "topic": topic,
                    "noecho": True,
                    "content": text,
                }
            },
            wait=True,
            timeout=30.0,
        )

    async def note_read(self, topic: str, seq: int | None = None) -> None:
        body: dict[str, Any] = {"topic": topic, "what": "read"}
        if seq is not None:
            body["seq"] = seq
        await self.send({"note": body}, wait=False)

    def _resolve_pending(self, ctrl: dict[str, Any]) -> None:
        mid = ctrl.get("id")
        if mid is None:
            return
        fut = self._pending.get(str(mid))
        if fut and not fut.done():
            fut.set_result(ctrl)

    def _is_live_message(self, data: dict[str, Any]) -> bool:
        if self.ready_at <= 0:
            return False
        ts = data.get("ts")
        if not ts:
            return True
        try:
            from datetime import datetime

            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt.timestamp() >= self.ready_at - 1.0
        except Exception:  # noqa: BLE001
            return True
        return True

    def _should_track_topic(self, topic: str | None) -> bool:
        if not topic:
            return False
        t = str(topic)
        # p2p + 群组；跳过 me/fnd/sys/频道广播可按需
        if t.startswith("usr") and t != self.user_id:
            return True
        if t.startswith("grp"):
            return True
        return False

    async def _handle_packet(self, pkt: dict[str, Any]) -> None:
        if "ctrl" in pkt:
            self._resolve_pending(pkt["ctrl"])
            return
        if "meta" in pkt:
            meta = pkt["meta"]
            topic = meta.get("topic")
            if topic == "me" and meta.get("sub"):
                for sub in meta["sub"]:
                    t = sub.get("topic")
                    if self._should_track_topic(t):
                        asyncio.create_task(self._safe_sub(t))
            return
        if "pres" in pkt:
            pres = pkt["pres"]
            src = pres.get("src")
            what = pres.get("what")
            # 被拉进群 / 新消息 / 权限变化
            if what in ("on", "msg", "acs", "upd", "gone") and src:
                if self._should_track_topic(src) and src not in self._subscribed:
                    asyncio.create_task(self._safe_sub(src))
            return
        if "data" in pkt:
            data = pkt["data"]
            topic = data.get("topic")
            if not topic:
                return
            if data.get("from") == self.user_id:
                return
            if not self._should_track_topic(topic):
                return
            if not self._is_live_message(data):
                return
            asyncio.create_task(self._safe_on_data(topic, data))

    async def _safe_sub(self, topic: str) -> None:
        try:
            await self.subscribe_topic(topic)
        except Exception as e:  # noqa: BLE001
            log.warning("[%s] 订阅任务 %s 失败：%s", self.username, topic, e)

    async def _safe_on_data(self, topic: str, data: dict[str, Any]) -> None:
        try:
            await self.on_data(self, topic, data)
        except Exception:  # noqa: BLE001
            log.exception("[%s] 处理消息失败，主题=%s", self.username, topic)

    async def _reader_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                if self._closed.is_set():
                    break
                try:
                    pkt = json.loads(raw)
                except json.JSONDecodeError:
                    log.warning("[%s] 收到无效 JSON：%s", self.username, str(raw)[:120])
                    continue
                await self._handle_packet(pkt)
        except Exception as e:  # noqa: BLE001
            if not self._closed.is_set():
                log.warning("[%s] 读取任务已停止：%s", self.username, e)
                for fut in list(self._pending.values()):
                    if not fut.done():
                        fut.set_exception(ConnectionError(str(e)))
        finally:
            self._closed.set()

    async def run_forever(self) -> None:
        if self._reader_task:
            await self._reader_task
        else:
            await self._closed.wait()

    async def close(self) -> None:
        self._closed.set()
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass
            self._ws = None
