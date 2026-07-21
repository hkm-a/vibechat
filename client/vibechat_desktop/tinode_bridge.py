"""Tinode 异步桥：在后台线程跑 asyncio，经 Qt Signal 回主线程。"""

from __future__ import annotations

import asyncio
import base64
import itertools
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QObject, Signal

log = logging.getLogger("desktop.tinode")

DEFAULT_API_KEY = "AQEAAAABAAD_rAp4DJh05a1HAwFT3A6K"


def basic_secret(username: str, password: str) -> str:
    return base64.b64encode(f"{username}:{password}".encode()).decode("ascii")


def content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict) and isinstance(content.get("txt"), str):
        return content["txt"]
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        return str(content)


@dataclass
class TopicInfo:
    topic: str
    title: str = ""
    is_group: bool = False
    last: str = ""
    seq: int = 0
    members: list[dict] = field(default_factory=list)


class TinodeBridge(QObject):
    """Qt 可订阅的 Tinode 会话。"""

    signed_in = Signal(str, str)  # user_id, display_name
    signed_out = Signal(str)  # reason
    error = Signal(str)
    topics_changed = Signal()
    messages_changed = Signal(str)  # topic
    search_results = Signal(list)  # [{user, fn}]
    group_created = Signal(str)
    status = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ws = None
        self._id_seq = itertools.count(1)
        self._pending: dict[str, asyncio.Future] = {}
        self._user_id: str | None = None
        self._me_name: str = ""
        self.topics: dict[str, TopicInfo] = {}
        self.messages: dict[str, list[dict]] = {}
        self._api_key = DEFAULT_API_KEY
        self._closed = threading.Event()

    # —— 线程控制 ——
    def start_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._closed.clear()
        self._thread = threading.Thread(target=self._thread_main, name="tinode-bridge", daemon=True)
        self._thread.start()

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            try:
                self._loop.close()
            except Exception:  # noqa: BLE001
                pass

    def _submit(self, coro):
        if not self._loop:
            raise RuntimeError("bridge not started")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def stop(self) -> None:
        if self._loop:
            fut = self._submit(self._disconnect())
            try:
                fut.result(timeout=5)
            except Exception:  # noqa: BLE001
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._closed.set()

    # —— 对外 API（线程安全）——
    def login(self, host: str, username: str, password: str, *, ssl: bool = False) -> None:
        self.start_thread()
        self._submit(self._login(host, username, password, ssl=ssl))

    def logout(self) -> None:
        self._submit(self._disconnect())

    def open_topic(self, topic: str) -> None:
        self._submit(self._open_topic(topic))

    def send_text(self, topic: str, text: str) -> None:
        self._submit(self._publish(topic, text))

    def search(self, query: str) -> None:
        self._submit(self._search(query))

    def create_group(self, name: str, member_ids: list[str]) -> None:
        self._submit(self._create_group(name, member_ids))

    def add_member(self, topic: str, user: str) -> None:
        self._submit(self._add_member(topic, user))

    def refresh_members(self, topic: str) -> None:
        self._submit(self._sub(topic, "desc sub"))

    # —— 协议实现 ——
    async def _ws_connect(self, url: str):
        try:
            from websockets.asyncio.client import connect as ws_connect
        except ImportError:
            from websockets import connect as ws_connect  # type: ignore
        return await ws_connect(url, open_timeout=20, max_size=4 * 1024 * 1024, ping_interval=20)

    def _next_id(self) -> str:
        return str(next(self._id_seq))

    async def _send(self, pkt: dict, *, wait: bool = False, timeout: float = 20.0):
        assert self._ws is not None
        wait_id = None
        for _k, body in list(pkt.items()):
            if isinstance(body, dict) and "id" not in body:
                body["id"] = self._next_id()
            if wait and isinstance(body, dict) and "id" in body:
                wait_id = str(body["id"])
        fut = None
        if wait and wait_id:
            fut = self._loop.create_future()  # type: ignore
            self._pending[wait_id] = fut
        await self._ws.send(json.dumps(pkt, ensure_ascii=False))
        if not fut:
            return None
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending.pop(wait_id or "", None)

    async def _login(self, host: str, username: str, password: str, *, ssl: bool) -> None:
        try:
            await self._disconnect()
            proto = "wss" if ssl else "ws"
            url = f"{proto}://{host}/v0/channels?apikey={self._api_key}"
            self.status.emit(f"连接 {host}…")
            self._ws = await self._ws_connect(url)
            self._id_seq = itertools.count(1)
            asyncio.create_task(self._reader())
            hi = await self._send({"hi": {"ver": "0.22", "ua": "VibeChat-Desktop/0.2", "lang": "zh-CN"}}, wait=True)
            if not hi or hi.get("code", 500) >= 400:
                raise RuntimeError(f"握手失败: {hi}")
            login = await self._send(
                {"login": {"scheme": "basic", "secret": basic_secret(username, password)}},
                wait=True,
            )
            if not login or login.get("code", 500) >= 400:
                raise RuntimeError("登录失败（账号或密码错误）")
            self._user_id = (login.get("params") or {}).get("user")
            me = await self._send({"sub": {"topic": "me", "get": {"what": "sub desc"}}}, wait=True)
            if not me or me.get("code", 500) >= 400:
                raise RuntimeError(f"订阅 me 失败: {me}")
            await self._send({"sub": {"topic": "fnd"}}, wait=True)
            self.status.emit("已登录")
            self.signed_in.emit(self._user_id or "", self._me_name or username)
        except Exception as e:  # noqa: BLE001
            log.exception("login failed")
            self.error.emit(str(e))
            await self._disconnect()

    async def _disconnect(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass
            self._ws = None
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(ConnectionError("disconnected"))
        self._pending.clear()

    async def _reader(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                try:
                    pkt = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await self._handle(pkt)
        except Exception as e:  # noqa: BLE001
            self.signed_out.emit(str(e))
        finally:
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.set_exception(ConnectionError("reader stopped"))

    async def _handle(self, pkt: dict) -> None:
        if "ctrl" in pkt:
            ctrl = pkt["ctrl"]
            mid = ctrl.get("id")
            if mid is not None:
                fut = self._pending.get(str(mid))
                if fut and not fut.done():
                    fut.set_result(ctrl)
            return
        if "meta" in pkt:
            self._on_meta(pkt["meta"])
            return
        if "data" in pkt:
            self._on_data(pkt["data"])
            return
        if "pres" in pkt:
            pres = pkt["pres"]
            src = pres.get("src")
            what = pres.get("what")
            if src and what in ("on", "msg", "acs", "upd"):
                if str(src).startswith(("usr", "grp")):
                    asyncio.create_task(self._sub(src, "desc sub"))

    def _ensure_topic(self, topic: str, **patch) -> TopicInfo:
        if topic not in self.topics:
            self.topics[topic] = TopicInfo(
                topic=topic,
                is_group=str(topic).startswith("grp"),
                title=topic,
            )
        t = self.topics[topic]
        for k, v in patch.items():
            setattr(t, k, v)
        return t

    def _on_meta(self, meta: dict) -> None:
        topic = meta.get("topic")
        if topic == "fnd" and meta.get("sub"):
            results = []
            for s in meta["sub"]:
                user = s.get("user") or s.get("topic")
                if not user or user == self._user_id:
                    continue
                fn = ((s.get("public") or {}).get("fn")) or user
                results.append({"user": user, "fn": fn})
            self.search_results.emit(results)
            return
        if topic == "me":
            if meta.get("desc"):
                self._me_name = ((meta["desc"].get("public") or {}).get("fn")) or self._me_name
            if meta.get("sub"):
                for sub in meta["sub"]:
                    t = sub.get("topic")
                    if not t or t == "fnd":
                        continue
                    public = sub.get("public") or {}
                    self._ensure_topic(
                        t,
                        title=public.get("fn") or t,
                        is_group=str(t).startswith("grp"),
                        seq=sub.get("seq") or 0,
                    )
                self.topics_changed.emit()
            return
        if topic and topic not in ("me", "fnd"):
            if meta.get("desc"):
                public = meta["desc"].get("public") or {}
                self._ensure_topic(topic, title=public.get("fn") or topic)
                self.topics_changed.emit()
            if meta.get("sub") and str(topic).startswith("grp"):
                self._ensure_topic(topic, members=list(meta["sub"]))
                self.topics_changed.emit()

    def _on_data(self, data: dict) -> None:
        topic = data.get("topic")
        if not topic:
            return
        text = content_to_text(data.get("content"))
        me = data.get("from") == self._user_id
        arr = self.messages.setdefault(topic, [])
        seq = data.get("seq")
        if seq is not None and any(m.get("seq") == seq for m in arr):
            return
        arr.append(
            {
                "from": data.get("from"),
                "content": text,
                "seq": seq,
                "ts": data.get("ts"),
                "me": me,
            }
        )
        t = self._ensure_topic(topic, last=text, seq=max(self.topics.get(topic, TopicInfo(topic)).seq, seq or 0))
        if not t.title or t.title == topic:
            # keep
            pass
        self.topics_changed.emit()
        self.messages_changed.emit(topic)

    async def _sub(self, topic: str, what: str = "desc sub data") -> dict | None:
        self._ensure_topic(topic)
        ctrl = await self._send(
            {"sub": {"topic": topic, "get": {"what": what, "data": {"limit": 40}}}},
            wait=True,
        )
        if ctrl and ctrl.get("code", 500) >= 400 and ctrl.get("code") != 304:
            raise RuntimeError(ctrl.get("text") or "订阅失败")
        return ctrl

    async def _open_topic(self, topic: str) -> None:
        try:
            self.messages[topic] = []
            await self._sub(topic, "desc sub data")
            self.messages_changed.emit(topic)
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))

    async def _publish(self, topic: str, text: str) -> None:
        try:
            text = (text or "").strip()
            if not text:
                return
            ctrl = await self._send({"pub": {"topic": topic, "content": text}}, wait=True)
            if not ctrl or ctrl.get("code", 500) >= 400:
                raise RuntimeError((ctrl or {}).get("text") or "发送失败")
            # 乐观本地显示
            arr = self.messages.setdefault(topic, [])
            arr.append({"from": self._user_id, "content": text, "seq": None, "ts": None, "me": True})
            self._ensure_topic(topic, last=text)
            self.topics_changed.emit()
            self.messages_changed.emit(topic)
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))

    async def _search(self, query: str) -> None:
        try:
            q = (query or "").trim() if False else (query or "").strip()
            if not q:
                self.search_results.emit([])
                return
            variants = [q, f"alias:{q}", f"{q},alias:{q}"]
            last: list = []
            for private in variants:
                await self._send({"set": {"topic": "fnd", "sub": {"private": private}}}, wait=True)
                await self._send({"get": {"topic": "fnd", "what": "sub"}}, wait=True)
                await asyncio.sleep(0.35)
                # results arrive via meta → search_results; keep last non-empty by waiting
            # 给 meta 一点时间
            await asyncio.sleep(0.2)
        except Exception as e:  # noqa: BLE001
            self.error.emit(f"搜索失败: {e}")
            self.search_results.emit([])

    async def _create_group(self, name: str, member_ids: list[str]) -> None:
        try:
            name = (name or "").strip()
            if not name:
                raise RuntimeError("群名称不能为空")
            if not member_ids:
                raise RuntimeError("请至少选择一位成员")
            set_body = {
                "desc": {"public": {"fn": name}},
                "sub": [{"user": u} for u in member_ids],
            }
            ctrl = await self._send(
                {"sub": {"topic": "new", "set": set_body, "get": {"what": "desc sub"}}},
                wait=True,
                timeout=30,
            )
            if not ctrl or ctrl.get("code", 500) >= 400:
                raise RuntimeError((ctrl or {}).get("text") or "建群失败")
            topic = ctrl.get("topic")
            if not topic:
                raise RuntimeError("建群未返回 topic")
            self._ensure_topic(topic, title=name, is_group=True)
            self.topics_changed.emit()
            self.group_created.emit(topic)
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))

    async def _add_member(self, topic: str, user: str) -> None:
        try:
            ctrl = await self._send({"set": {"topic": topic, "sub": {"user": user}}}, wait=True)
            if not ctrl or ctrl.get("code", 500) >= 400:
                raise RuntimeError((ctrl or {}).get("text") or "添加失败")
            await self._sub(topic, "desc sub")
            self.status.emit(f"已添加成员 {user}")
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))