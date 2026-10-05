"""Render the app icon (WorldSync orbit badge) to app/assets/icon.ico + icon.png.

Run once:  .venv\\Scripts\\python.exe tools\\generate_icon.py
"""

import io
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "app" / "assets"

ICON_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <defs>
    <radialGradient id="glow" cx="50%" cy="45%" r="60%">
      <stop offset="0%" stop-color="#7A9BFF" stop-opacity="0.35"/>
      <stop offset="60%" stop-color="#7A9BFF" stop-opacity="0.08"/>
      <stop offset="100%" stop-color="#7A9BFF" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="planet" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#A9BEFF"/>
      <stop offset="100%" stop-color="#4562E0"/>
    </linearGradient>
    <linearGradient id="ring" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#5CD6C9"/>
      <stop offset="100%" stop-color="#F2B66B"/>
    </linearGradient>
    <clipPath id="front">
      <rect x="0" y="128" width="256" height="128"/>
    </clipPath>
  </defs>

  <rect x="6" y="6" width="244" height="244" rx="58" fill="#0B0F1E"/>
  <rect x="6" y="6" width="244" height="244" rx="58" fill="url(#glow)"/>
  <rect x="8" y="8" width="240" height="240" rx="56" fill="none"
        stroke="#232B48" stroke-width="3"/>

  <!-- back half of the orbit, behind the planet -->
  <ellipse cx="128" cy="128" rx="98" ry="34" transform="rotate(-22 128 128)"
           fill="none" stroke="url(#ring)" stroke-width="12" stroke-opacity="0.55"/>
  <!-- planet -->
  <circle cx="128" cy="128" r="54" fill="url(#planet)"/>
  <path d="M 86 108 C 104 118, 150 118, 172 104 M 80 140 C 106 154, 152 154, 176 138"
        fill="none" stroke="#0B0F1E" stroke-opacity="0.28" stroke-width="7"
        stroke-linecap="round"/>
  <!-- front half of the orbit, over the planet -->
  <g clip-path="url(#front)" transform="rotate(-22 128 128)">
    <ellipse cx="128" cy="128" rx="98" ry="34" fill="none"
             stroke="url(#ring)" stroke-width="12"/>
  </g>
  <!-- two friends in orbit -->
  <circle cx="214" cy="90" r="16" fill="#F2B66B"/>
  <circle cx="42" cy="166" r="16" fill="#5CD6C9"/>
</svg>
"""


def render_png(size: int) -> Image.Image:
    renderer = QSvgRenderer(QByteArray(ICON_SVG.encode()))
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    renderer.render(p, QRectF(0, 0, size, size))
    p.end()
    buf = io.BytesIO()
    img.save_to_buffer = None  # noqa - QImage has no direct PIL bridge; go via bytes
    ba = QByteArray()
    from PySide6.QtCore import QBuffer, QIODevice
    qbuf = QBuffer(ba)
    qbuf.open(QIODevice.WriteOnly)
    img.save(qbuf, "PNG")
    buf.write(bytes(ba))
    buf.seek(0)
    return Image.open(buf).convert("RGBA")


def main():
    QGuiApplication(sys.argv)
    ASSETS.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = {s: render_png(s) for s in sizes}
    images[256].save(ASSETS / "icon.png")
    images[256].save(
        ASSETS / "icon.ico", format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=[images[s] for s in sizes if s != 256],
    )
    (ASSETS / "icon.svg").write_text(ICON_SVG, encoding="utf-8")
    print(f"Wrote {ASSETS / 'icon.ico'} ({sizes})")


if __name__ == "__main__":
    main()
