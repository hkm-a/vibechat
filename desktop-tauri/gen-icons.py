#!/usr/bin/env python3
"""Generate icons for VibeChat Tauri bundles (all platforms)."""
from pathlib import Path
import struct, zlib

OUT = Path(__file__).resolve().parent / "src-tauri" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

# brand colors
BG = (15, 17, 23)       # #0f1117
ACCENT = (99, 102, 241)  # #6366f1
FG = (255, 255, 255)

def make_png(size: int, color: tuple[int, ...], path: Path):
    r, g, b = color[0], color[1], color[2]
    raw = b''
    for y in range(size):
        raw += b'\x00'  # filter byte
        for x in range(size):
            # simple gradient: V shape
            cx, cy = size // 2, size // 2
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            t = min(1.0, d / (size * 0.6))
            rr = int(r + (255 - r) * t * 0.3)
            gg = int(g + (255 - g) * t * 0.3)
            bb = int(b + (255 - b) * t * 0.3)
            raw += bytes([rr, gg, bb, 255])

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', ihdr)
    png += chunk(b'IDAT', zlib.compress(raw, 9))
    png += chunk(b'IEND', b'')
    path.write_bytes(png)
    print(f'  {path.name}  {size}x{size}')

# .png icons
for sz, name in [(32, '32x32.png'), (128, '128x128.png'), (256, '128x128@2x.png'), (512, 'icon.png')]:
    make_png(sz, ACCENT, OUT / name)

# .ico (Windows): embed 32x32 png
png32 = (OUT / '32x32.png').read_bytes()
header = struct.pack('<HHH', 0, 1, 1)
entry = struct.pack('<BBBBHHII', 32, 32, 0, 0, 1, 32, len(png32), 22)
(OUT / 'icon.ico').write_bytes(header + entry + png32)
print('  icon.ico')

# .icns (macOS): wrap 128x128 png as icns icon
png128 = (OUT / '128x128.png').read_bytes()
icns_type = b'ic07'  # 128x128 PNG
entry_data = icns_type + struct.pack('>I', 8 + len(png128)) + png128
icns = b'icns' + struct.pack('>I', 8 + len(entry_data)) + entry_data
(OUT / 'icon.icns').write_bytes(icns)
print('  icon.icns')

print('OK - all icons regenerated')