"""Agnes OpenAI 兼容 Chat Completions（含模型回退）。"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Sequence

log = logging.getLogger("npc.agnes")


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class AgnesClient:
    base_url: str
    api_key: str
    primary_model: str
    fallback_model: str
    max_tokens: int = 512
    temperature: float = 0.8
    timeout_sec: float = 90.0

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        models = [self.primary_model]
        if self.fallback_model and self.fallback_model != self.primary_model:
            models.append(self.fallback_model)

        last_err: Exception | None = None
        for model in models:
            for tokens in (self.max_tokens, max(self.max_tokens, 768), 1024):
                try:
                    text = self._request(model, messages, max_tokens=tokens)
                    if text.strip():
                        return text.strip()
                    log.warning("model %s empty content (max_tokens=%s)", model, tokens)
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    log.warning("model %s failed: %s", model, e)
                    break  # 换模型，不必抬 max_tokens
        if last_err:
            log.error("all models failed, last=%s", last_err)
        return "嗯，我这边信号不太好，再说一次？"

    def _request(self, model: str, messages: Sequence[ChatMessage], *, max_tokens: int) -> str:
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
            # 尽量抑制 thinking 吃满额度；部分网关会忽略
            "chat_template_kwargs": {"enable_thinking": False},
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"HTTP {e.code}: {detail}") from e

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"no choices: {str(data)[:300]}")
        msg = choices[0].get("message") or {}
        content = _normalize_content(msg.get("content"))
        if content.strip():
            return content
        # 少数渠道把可见输出塞进 reasoning_content 末尾
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
        if isinstance(reasoning, str) and reasoning.strip():
            tail = _guess_answer_from_reasoning(reasoning)
            if tail:
                return tail
        return ""


def _normalize_content(content) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _guess_answer_from_reasoning(reasoning: str) -> str:
    """从 thinking 文本里捞最后一句像回复的中文（兜底）。"""
    # 优先找 ``` 之后或 "Final answer" 类标记
    for pat in (
        r"(?:Final Answer|最终回复|最终答案|回复)[:：\s]*\n*(.+)$",
        r"\"([^\"]{2,80})\"\s*$",
    ):
        m = re.search(pat, reasoning, re.I | re.S)
        if m:
            cand = m.group(1).strip()
            if cand and "thinking" not in cand.lower():
                return cand.splitlines()[0][:200]
    # 取最后一行非英文分析的中文短句
    for line in reversed(reasoning.splitlines()):
        line = line.strip(" -\t")
        if not line or line.startswith(("1.", "2.", "-", "*", "#")):
            continue
        if re.search(r"[\u4e00-\u9fff]", line) and len(line) <= 120:
            if "Analyze" in line or "User" in line:
                continue
            return line
    return ""


def build_messages(
    system: str,
    history: Iterable[tuple[str, str]],
    *,
    history_limit: int,
) -> list[ChatMessage]:
    """history: (role, text) role in {user, assistant}。"""
    tail = list(history)[-history_limit:]
    out = [ChatMessage(role="system", content=system)]
    for role, text in tail:
        if text and text.strip():
            out.append(ChatMessage(role=role, content=text.strip()))
    return out