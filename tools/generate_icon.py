"""Render the app icon (dragon-eye badge) to app/assets/icon.ico + icon.png.

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
    <radialGradient id="glow" cx="50%" cy="42%" r="62%">
      <stop offset="0%" stop-color="#3ECF8E" stop-opacity="0.30"/>
      <stop offset="55%" stop-color="#3ECF8E" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="#3ECF8E" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="fire" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#4ADD9B"/>
      <stop offset="100%" stop-color="#1FA89B"/>
    </linearGradient>
    <linearGradient id="slit" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#5BE7AC"/>
      <stop offset="100%" stop-color="#1FA89B"/>
    </linearGradient>
  </defs>

  <rect x="6" y="6" width="244" height="244" rx="58" fill="#0C1116"/>
  <rect x="6" y="6" width="244" height="244" rx="58" fill="url(#glow)"/>
  <rect x="8" y="8" width="240" height="240" rx="56" fill="none"
        stroke="#26333F" stroke-width="3"/>

  <!-- almond eye -->
  <path d="M 38 128 C 72 74, 184 74, 218 128 C 184 182, 72 182, 38 128 Z"
        fill="#3ECF8E" fill-opacity="0.07"
        stroke="url(#fire)" stroke-width="11" stroke-linejoin="round"/>

  <!-- slit pupil -->
  <path d="M 128 86 C 142 103, 142 153, 128 170 C 114 153, 114 103, 128 86 Z"
        fill="url(#slit)"/>

  <!-- glint -->
  <circle cx="139" cy="105" r="8" fill="#EAFBF2" fill-opacity="0.9"/>
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
