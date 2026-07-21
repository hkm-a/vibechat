"""从 Tinode 消息 content（字符串 / Drafty）提取纯文本。"""

from __future__ import annotations

from typing import Any


def content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (int, float, bool)):
        return str(content)
    if isinstance(content, dict):
        # Drafty: {txt, fmt, ent, ...}
        txt = content.get("txt")
        if isinstance(txt, str) and txt.strip():
            return txt
        # 少数实现把正文放在 content
        inner = content.get("content")
        if inner is not None and inner is not content:
            return content_to_text(inner)
        return ""
    if isinstance(content, list):
        return " ".join(content_to_text(x) for x in content if x is not None).strip()
    return str(content)