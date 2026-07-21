#!/usr/bin/env python3
"""将 branding/static 中的 Tinode 可见品牌改为 VibeChat。

用法：
  1. 从运行中的容器同步一份原版静态资源（首次或升级镜像后）：
       sudo docker cp tinode-srv:/opt/tinode/static ./branding/static
  2. python3 branding/apply-brand.py
  3. sudo docker compose restart tinode
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "static"
BRAND = "VibeChat"
THEME = "#6366F1"
DESC = "VibeChat — self-hosted instant messenger"


def png_rgba(size: int, rgba_fn):
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            raw.extend(rgba_fn(x, y, size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def logo_pixel(x, y, size):
    nx, ny = x / (size - 1), y / (size - 1)
    r = int(0x81 + (0x63 - 0x81) * (nx + ny) / 2)
    g = int(0x8C + (0x66 - 0x8C) * (nx + ny) / 2)
    b = int(0xF8 + (0xF1 - 0xF8) * (nx + ny) / 2)
    rad = 0.22

    def in_round_rect(u, v):
        px, py = u * 2 - 1, v * 2 - 1
        ax, ay = abs(px), abs(py)
        if ax <= 1 - rad and ay <= 1 - rad:
            return True
        if ax > 1 - rad and ay > 1 - rad:
            cx, cy = 1 - rad, 1 - rad
            return (ax - cx) ** 2 + (ay - cy) ** 2 <= rad**2
        return ax <= 1 and ay <= 1

    if not in_round_rect(nx, ny):
        return (0, 0, 0, 0)

    def dist_to_segment(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        return ((px - (x1 + t * dx)) ** 2 + (py - (y1 + t * dy)) ** 2) ** 0.5

    d = min(
        dist_to_segment(nx, ny, 0.30, 0.32, 0.50, 0.74),
        dist_to_segment(nx, ny, 0.50, 0.74, 0.70, 0.32),
    )
    if d < 0.07:
        return (255, 255, 255, 245)
    if (nx - 0.72) ** 2 + (ny - 0.33) ** 2 < 0.012:
        return (253, 230, 138, 255)
    return (r, g, b, 255)


def strip_firebase_script(html: str) -> str:
    """本地未配置 FCM 时禁用前端推送初始化。

    镜像默认 FCM_PUSH_ENABLED=false（非空），entrypoint 仍会写出空 FIREBASE_INIT 对象，
    导致 Web 端报「初始化推送通知失败」。直接不加载该脚本最干净。
    """
    return html.replace('<script src="firebase-init.js"></script>\n', "")


def brand_js_tree() -> None:
    """替换 umd/ 下可见品牌字符串（含 code-split chunk）。"""
    umd = ROOT / "umd"
    if not umd.exists():
        return
    for path in umd.rglob("*.js"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        orig = text
        text = text.replace("Tinode Web", BRAND)
        text = text.replace('const i="TinodeWeb"', f'const i="{BRAND}"')
        text = text.replace("const BASE_APP_NAME = 'TinodeWeb'", f"const BASE_APP_NAME = '{BRAND}'")
        text = text.replace(
            'document.title=(e>0?"("+e+") ":"")+"Tinode"',
            f'document.title=(e>0?"("+e+") ":"")+"{BRAND}"',
        )
        text = text.replace(
            "document.title = (count > 0 ? '(' + count + ') ' : '') + 'Tinode'",
            f"document.title = (count > 0 ? '(' + count + ') ' : '') + '{BRAND}'",
        )
        if text != orig:
            path.write_text(text, encoding="utf-8")


def guard_service_worker() -> None:
    sw = ROOT / "service-worker.js"
    if not sw.exists():
        return
    text = sw.read_text(encoding="utf-8", errors="ignore")
    if "VIBECHAT_PUSH_GUARD" in text:
        return
    needle = "firebase.initializeApp(FIREBASE_INIT);\nconst fbMessaging = firebase.messaging();"
    if needle not in text:
        return
    # 无有效 FCM 配置时跳过；避免 SW 在本地启动时抛错
    text = text.replace(
        needle,
        """// VIBECHAT_PUSH_GUARD
const __vbPushReady = (typeof FIREBASE_INIT !== 'undefined')
  && FIREBASE_INIT
  && FIREBASE_INIT.apiKey
  && FIREBASE_INIT.projectId
  && FIREBASE_INIT.appId;
let fbMessaging = null;
if (__vbPushReady) {
  firebase.initializeApp(FIREBASE_INIT);
  fbMessaging = firebase.messaging();
}""",
        1,
    )
    text = text.replace(
        "fbMessaging.onBackgroundMessage(payload => {",
        "if (fbMessaging) fbMessaging.onBackgroundMessage(payload => {",
        1,
    )
    # 给 onBackgroundMessage 回调补上闭合括号（原代码以 }); 结束该调用）
    # 上面 if 包裹后，原 `});` 仍正确结束 if 块内的调用。
    sw.write_text(text, encoding="utf-8")


def main() -> None:
    if not ROOT.exists():
        raise SystemExit(f"missing static dir: {ROOT}")

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    for a, b in {
        "<title>Tinode</title>": f"<title>{BRAND}</title>",
        'content="Tinode Web"': f'content="{BRAND}"',
        'content="Tinode instant messenger in a browser"': f'content="{DESC}"',
        'content="https://web.tinode.co/"': 'content="/"',
        'og:title" content="Tinode Web"': f'og:title" content="{BRAND}"',
        'og:description" content="Tinode instant messenger in a browser"': f'og:description" content="{DESC}"',
        'href="https://web.tinode.co/"': 'href="/"',
        "TinodeWeb does not work without JavaScript.": f"{BRAND} does not work without JavaScript.",
        'content="#3949AB"': f'content="{THEME}"',
        "img/og-logo.jpeg": "img/og-logo.png",
    }.items():
        html = html.replace(a, b)
    # already branded re-run: keep VibeChat
    html = html.replace("<title>Tinode</title>", f"<title>{BRAND}</title>")
    html = strip_firebase_script(html)
    # 缓存破坏：服务端 cache_control 很长，品牌更新后强制浏览器拉新 JS
    if "umd/index.prod.js?v=" not in html:
        html = html.replace('src="umd/tinode.prod.js"', 'src="umd/tinode.prod.js?v=vibechat1"')
        html = html.replace('src="umd/index.prod.js"', 'src="umd/index.prod.js?v=vibechat1"')
    (ROOT / "index.html").write_text(html, encoding="utf-8")

    if (ROOT / "index-dev.html").exists():
        dev = (ROOT / "index-dev.html").read_text(encoding="utf-8")
        for a, b in {
            "<title>Tinode</title>": f"<title>{BRAND}</title>",
            'content="Tinode Web, version for developers"': f'content="{BRAND} (dev)"',
            'content="Tinode instant messenger, development version"': f'content="{DESC} (dev)"',
            'content="Tinode Web Development"': f'content="{BRAND} Dev"',
            "TinodeWeb does not work without JavaScript.": f"{BRAND} does not work without JavaScript.",
            'content="#3949AB"': f'content="{THEME}"',
        }.items():
            dev = dev.replace(a, b)
        dev = strip_firebase_script(dev)
        (ROOT / "index-dev.html").write_text(dev, encoding="utf-8")

    (ROOT / "manifest.json").write_text(
        f"""{{
  "name": "{BRAND}",
  "short_name": "{BRAND}",
  "description": "{DESC}",
  "categories": ["chat", "communication", "productivity"],
  "icons": [
    {{"src": "img/logo96.png", "sizes": "96x96", "type": "image/png"}},
    {{"src": "img/logo192.png", "sizes": "192x192", "type": "image/png"}},
    {{"src": "img/logo.svg", "type": "image/svg+xml", "sizes": "512x512"}}
  ],
  "start_url": "/",
  "background_color": "#0f172a",
  "theme_color": "{THEME}",
  "display": "standalone",
  "prefer_related_applications": false,
  "permissions": {{
    "audio-capture": {{"description": "Required for recording voice messages"}}
  }}
}}
""",
        encoding="utf-8",
    )

    brand_js_tree()
    guard_service_worker()

    #  bump SW 缓存桶：旧 service-worker 会强缓存静态资源，导致仍见 Tinode / 推送错误
    ver = ROOT / "version.js"
    if ver.exists():
        ver.write_text(
            '// This is a generated file. Don\'t edit.\n\n'
            'const PACKAGE_VERSION = "0.25.3-vibechat1";\n',
            encoding="utf-8",
        )

    # 兜底：即使 entrypoint 写出空配置对象，也尽量写成“未定义”
    # （容器重启后会被 entrypoint 覆盖；真正禁用靠 index.html 不加载该脚本）
    (ROOT / "firebase-init.js").write_text(
        "// push disabled for local VibeChat\n",
        encoding="utf-8",
    )

    (ROOT / "img" / "logo.svg").write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="{BRAND}">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#818CF8"/>
      <stop offset="100%" stop-color="{THEME}"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="112" fill="url(#g)"/>
  <path d="M156 150h200c18 0 28 20 16 34L286 300v62c0 12-10 22-22 22h-16c-12 0-22-10-22-22v-62L140 184c-12-14-2-34 16-34z" fill="#fff" opacity=".95"/>
  <circle cx="368" cy="168" r="28" fill="#FDE68A"/>
</svg>
""",
        encoding="utf-8",
    )

    for size, name in [
        (32, "logo32x32.png"),
        (32, "logo32x32a.png"),
        (96, "logo96.png"),
        (192, "logo192.png"),
        (96, "badge96.png"),
        (512, "og-logo.png"),
    ]:
        (ROOT / "img" / name).write_bytes(png_rgba(size, logo_pixel))

    print(f"brand -> {BRAND} applied under {ROOT}")


if __name__ == "__main__":
    main()