"""Procedural world-art hero banner.

No bundled image files — every world's landscape is painted from a seed
derived from its name, so each world looks distinct and consistent across
runs and machines. Layered ridge silhouettes, a moon with a soft halo, mist
bands, and a few drifting embers, all tinted by the world's accent colour.
A bottom scrim keeps the overlaid title legible and blends into the app.
"""

import hashlib
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QLinearGradient, QPainter,
                           QPainterPath, QRadialGradient)
from PySide6.QtWidgets import QWidget

from . import theme

RIDGE_LAYERS = 4
EMBER_COUNT = 16


def _seed(world_name: str) -> int:
    digest = hashlib.sha1((world_name or "wilds").encode("utf-8")).digest()
    return int.from_bytes(digest[:6], "big")


class WorldBanner(QWidget):
    def __init__(self, height=168, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self._world = ""
        self._accent = QColor(theme.ACCENT)
        self._ridges: list[list[QPointF]] = []
        self._moon = (0.72, 0.4, 26.0)   # x-frac, y-frac, radius
        self._cache_key = None
        self._embers = []
        self._t = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(40)   # ~25 fps, gentle
        self._timer.timeout.connect(self._tick)

    # -- public ------------------------------------------------------------
    def set_world(self, world_name: str, accent: str | None = None):
        self._world = world_name or ""
        if accent:
            c = QColor(accent)
            if c.isValid():
                self._accent = c
        self._cache_key = None
        self.update()

    # -- lifecycle ---------------------------------------------------------
    def showEvent(self, e):
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def _tick(self):
        self._t += 0.04
        for em in self._embers:
            em["y"] -= em["speed"]
            em["x"] += math.sin(self._t * em["drift"] + em["phase"]) * 0.15
            if em["y"] < -0.05:
                em["y"] = 1.05
                em["x"] = random.random()
        self.update()

    # -- scene build (cached per size+seed) --------------------------------
    def _rebuild(self, w, h):
        rng = random.Random(_seed(self._world))
        self._ridges = []
        for layer in range(RIDGE_LAYERS):
            pts = []
            # nearer layers sit lower and are jaggier
            base = 0.30 + layer * 0.17
            rough = 0.05 + layer * 0.05
            steps = 7 + layer * 3
            for i in range(steps + 1):
                x = i / steps
                y = base + (rng.random() - 0.5) * rough * 2 \
                    + math.sin(x * math.pi * (1 + layer)) * 0.03 * (rng.random() + 0.4)
                pts.append(QPointF(x * w, y * h))
            self._ridges.append(pts)
        self._moon = (0.18 + rng.random() * 0.64, 0.26 + rng.random() * 0.18,
                      20.0 + rng.random() * 12.0)
        self._embers = [{
            "x": rng.random(), "y": rng.random(),
            "speed": 0.0016 + rng.random() * 0.0034,
            "size": 1.0 + rng.random() * 2.2,
            "phase": rng.random() * 6.28, "drift": 0.6 + rng.random() * 1.2,
        } for _ in range(EMBER_COUNT)]
        self._cache_key = (w, h, self._world)

    # -- painting ----------------------------------------------------------
    def paintEvent(self, e):
        w, h = self.width(), self.height()
        if self._cache_key != (w, h, self._world):
            self._rebuild(w, h)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        hue = self._accent.hueF()
        if hue < 0:
            hue = 0.42

        # rounded-top clip so the banner tucks under the titlebar cleanly
        clip = QPainterPath()
        clip.addRect(QRectF(0, 0, w, h))
        p.setClipPath(clip)

        # sky
        sky = QLinearGradient(0, 0, 0, h)
        sky.setColorAt(0.0, QColor.fromHsvF(hue, 0.55, 0.20))
        sky.setColorAt(0.55, QColor.fromHsvF((hue + 0.03) % 1.0, 0.5, 0.09))
        sky.setColorAt(1.0, QColor("#070A0E"))
        p.fillRect(self.rect(), QBrush(sky))

        # moon + halo
        mx, my, mr = self._moon
        cx, cy = mx * w, my * h
        halo = QRadialGradient(cx, cy, mr * 3.2)
        glow = QColor.fromHsvF(hue, 0.30, 1.0)
        glow.setAlphaF(0.28)
        halo.setColorAt(0.0, glow)
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(halo))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), mr * 3.2, mr * 3.2)
        disc = QColor.fromHsvF(hue, 0.12, 0.98)
        p.setBrush(QBrush(disc))
        p.drawEllipse(QPointF(cx, cy), mr, mr)

        # ridges, back (lighter, tinted) to front (near black)
        for i, pts in enumerate(self._ridges):
            t = i / (RIDGE_LAYERS - 1)
            val = 0.16 * (1 - t) + 0.03
            sat = 0.42 * (1 - t)
            color = QColor.fromHsvF(hue, sat, val)
            path = QPainterPath()
            path.moveTo(pts[0].x(), h)
            for pt in pts:
                path.lineTo(pt)
            path.lineTo(pts[-1].x(), h)
            path.closeSubpath()
            p.setBrush(QBrush(color))
            p.setPen(Qt.NoPen)
            p.drawPath(path)

        # embers rising in front of the ridges
        ember = QColor(theme.EMBER_HI)
        for em in self._embers:
            ex, ey = em["x"] * w, em["y"] * h
            if ey < h * 0.35:
                continue
            a = max(0.0, min(0.8, (em["y"] - 0.35) * 1.1))
            a *= 0.6 + 0.4 * math.sin(self._t * 2 + em["phase"])
            ember.setAlphaF(max(0.0, a))
            p.setBrush(QBrush(ember))
            p.drawEllipse(QPointF(ex, ey), em["size"], em["size"])

        # bottom scrim for text legibility + blend into app bg
        scrim = QLinearGradient(0, h * 0.35, 0, h)
        scrim.setColorAt(0.0, QColor(6, 9, 13, 0))
        scrim.setColorAt(0.72, QColor(6, 9, 13, 150))
        scrim.setColorAt(1.0, QColor(10, 13, 18, 235))
        p.fillRect(QRectF(0, h * 0.35, w, h * 0.65), QBrush(scrim))

        # faint vignette on the sides
        vign = QLinearGradient(0, 0, w, 0)
        vign.setColorAt(0.0, QColor(0, 0, 0, 90))
        vign.setColorAt(0.12, QColor(0, 0, 0, 0))
        vign.setColorAt(0.88, QColor(0, 0, 0, 0))
        vign.setColorAt(1.0, QColor(0, 0, 0, 90))
        p.fillRect(self.rect(), QBrush(vign))
        p.end()
