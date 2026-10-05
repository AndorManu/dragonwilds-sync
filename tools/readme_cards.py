"""Render the README's game cards (docs/readme/games/*.png) with the app's own
scenes, colours and typefaces, so the README matches the app exactly.

Run:  .venv\\Scripts\\python.exe tools\\readme_cards.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QLinearGradient, QPainter,  # noqa: E402
                           QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import games  # noqa: E402
from app.ui import gamethemes, scenes, theme  # noqa: E402

OUT = ROOT / "docs" / "readme" / "games"
W, H = 640, 240
S = 2   # supersample for crisp text


def card(profile) -> QPixmap:
    t = gamethemes.get(profile.id)
    tok = t.tokens()
    pm = QPixmap(W * S, H * S)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.scale(S, S)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, W, H), 22, 22)
    p.setClipPath(clip)
    art = scenes.render(t.scene, W, H, tok["ACCENT"], tok["EMBER"], seed=1234, t=3.0)
    p.drawPixmap(0, 0, art)
    shade = QLinearGradient(0, 0, W, 0)
    shade.setColorAt(0, QColor(0, 0, 0, 205))
    shade.setColorAt(0.55, QColor(0, 0, 0, 90))
    shade.setColorAt(1, QColor(0, 0, 0, 10))
    p.fillRect(QRectF(0, 0, W, H), shade)

    # status pill
    verified = profile.verified
    pill_color = QColor(tok["ACCENT"]) if verified else QColor(tok["EMBER"])
    f = QFont("Bahnschrift SemiBold")
    f.setPixelSize(15)
    f.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
    p.setFont(f)
    label = "TESTED" if verified else "BETA"
    pw = p.fontMetrics().horizontalAdvance(label) + 30
    fill = QColor(pill_color)
    fill.setAlpha(60)
    p.setPen(QPen(pill_color, 1.6))
    p.setBrush(fill)
    p.drawRoundedRect(QRectF(30, 34, pw, 30), 15, 15)
    p.setPen(QColor("#FFFFFF"))
    p.drawText(QRectF(30, 34, pw, 30), Qt.AlignCenter, label)

    # title in the game's own typeface
    title = QFont(theme._family(t.deco))
    size = 52 if len(profile.short) <= 12 else 40
    title.setPixelSize(size)
    title.setWeight(QFont.Bold)
    if t.title_spacing:
        title.setLetterSpacing(QFont.AbsoluteSpacing, min(t.title_spacing, 3) * 0.8)
    p.setFont(title)
    p.setPen(QColor("#FFFFFF"))
    name = profile.short.upper() if t.caps else profile.short
    p.drawText(QRectF(30, 84, W - 60, 80), Qt.AlignLeft | Qt.AlignVCenter, name)

    # accent bar + tagline
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(tok["ACCENT"]))
    p.drawRoundedRect(QRectF(30, 166, 120, 6), 3, 3)
    tf = QFont("Segoe UI")
    tf.setPixelSize(19)
    p.setFont(tf)
    p.setPen(QColor("#E6E9F0"))
    p.drawText(QRectF(30, 182, W - 60, 30), Qt.AlignLeft | Qt.AlignVCenter, profile.tagline)

    p.setClipping(False)
    p.setPen(QPen(QColor(255, 255, 255, 40), 1.5))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(0.75, 0.75, W - 1.5, H - 1.5), 22, 22)
    p.end()
    return pm


def main():
    app = QApplication(sys.argv)
    theme.apply(app)
    OUT.mkdir(parents=True, exist_ok=True)
    for g in games.ALL:
        card(g).save(str(OUT / f"{g.id}.png"))
        print("card", g.id)


if __name__ == "__main__":
    main()
