"""Procedural world-art hero banner.

No bundled image files: the active game's scene (scenes.py) is painted from
a seed derived from the world name, so each world looks distinct and
consistent across runs and machines. A bottom scrim keeps the overlaid
title legible and blends the art into the app background.
"""

import hashlib

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from . import scenes, theme


def _seed(world_name: str) -> int:
    digest = hashlib.sha1((world_name or "wilds").encode("utf-8")).digest()
    return int.from_bytes(digest[:6], "big")


class WorldBanner(QWidget):
    def __init__(self, height=168, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self._world = ""
        self._scene_id = None
        self._scene = None
        self._t = 0.0
        self.set_scene(theme.scene())

        self._timer = QTimer(self)
        self._timer.setInterval(40)   # ~25 fps, gentle
        self._timer.timeout.connect(self._tick)

    # -- public ------------------------------------------------------------
    def set_world(self, world_name: str, accent: str | None = None):
        self._world = world_name or ""
        self.update()

    def set_scene(self, scene_id: str):
        """Follow the active theme: its scene, accent and ember colours."""
        key = (scene_id, theme.ACCENT, theme.EMBER)
        if key == self._scene_id:
            return
        self._scene_id = key
        self._scene = scenes.make(scene_id, theme.ACCENT, theme.EMBER)
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
        self.update()

    # -- painting ----------------------------------------------------------
    def paintEvent(self, e):
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setClipRect(self.rect())
        self._scene.ensure(w, h, _seed(self._world))
        self._scene.paint(p, self._t)

        # bottom scrim for text legibility + blend into the app background
        bg = QColor(theme.BG)
        scrim = QLinearGradient(0, h * 0.35, 0, h)
        c0, c1, c2 = QColor(bg), QColor(bg), QColor(bg)
        c0.setAlpha(0)
        c1.setAlpha(150)
        c2.setAlpha(235)
        scrim.setColorAt(0.0, c0)
        scrim.setColorAt(0.72, c1)
        scrim.setColorAt(1.0, c2)
        p.fillRect(QRectF(0, h * 0.35, w, h * 0.65), QBrush(scrim))

        # faint vignette on the sides
        vign = QLinearGradient(0, 0, w, 0)
        vign.setColorAt(0.0, QColor(0, 0, 0, 90))
        vign.setColorAt(0.12, QColor(0, 0, 0, 0))
        vign.setColorAt(0.88, QColor(0, 0, 0, 0))
        vign.setColorAt(1.0, QColor(0, 0, 0, 90))
        p.fillRect(self.rect(), QBrush(vign))
        p.end()
