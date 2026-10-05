"""Procedural banner scenes, one per game.

No image files and no game assets: every scene is painted with QPainter from
a seed (the world name), so each world looks a little different but always
the same on every PC. A scene builds its static layout once per size and
seed, then ``paint`` draws a frame at time ``t`` (seconds, ~25 fps) for the
gentle motion: aurora, fog, waves, bats, ash.

The banner widget adds the bottom scrim and vignette on top, so scenes only
paint the world itself.
"""

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient)


def col(hex_color: str, alpha: float = 1.0) -> QColor:
    c = QColor(hex_color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def vgrad(p: QPainter, rect: QRectF, stops):
    g = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
    for at, c in stops:
        g.setColorAt(at, c if isinstance(c, QColor) else QColor(c))
    p.fillRect(rect, QBrush(g))


def glow(p: QPainter, x, y, r, color: QColor, core: float = 0.0):
    g = QRadialGradient(x, y, r)
    g.setColorAt(0.0, color)
    mid = QColor(color)
    mid.setAlphaF(color.alphaF() * 0.35)
    g.setColorAt(0.45, mid)
    g.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(x, y), r, r)
    if core:
        c = QColor(color)
        c.setAlphaF(1.0)
        p.setBrush(QBrush(c))
        p.drawEllipse(QPointF(x, y), core, core)


def ridge(rng, w, h, base, rough, steps, wave=0.03):
    pts = []
    for i in range(steps + 1):
        x = i / steps
        y = base + (rng.random() - 0.5) * rough * 2 + math.sin(x * math.pi * 2.3) * wave
        pts.append(QPointF(x * w, y * h))
    return pts


def fill_ridge(p: QPainter, pts, h, color: QColor):
    path = QPainterPath()
    path.moveTo(pts[0].x(), h)
    for pt in pts:
        path.lineTo(pt)
    path.lineTo(pts[-1].x(), h)
    path.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(color))
    p.drawPath(path)


def smooth_ridge(rng, w, h, base, amp, bumps):
    """A soft hill line built from cubic curves."""
    path = QPainterPath()
    path.moveTo(0, h)
    xs = [i * w / bumps for i in range(bumps + 1)]
    ys = [h * (base + (rng.random() - 0.5) * amp) for _ in xs]
    path.lineTo(xs[0], ys[0])
    for i in range(bumps):
        mx = (xs[i] + xs[i + 1]) / 2
        path.cubicTo(mx, ys[i], mx, ys[i + 1], xs[i + 1], ys[i + 1])
    path.lineTo(w, h)
    path.closeSubpath()
    return path


class Scene:
    """Base: subclasses fill build() and paint()."""
    particles = 0

    def __init__(self, accent: str, ember: str):
        self.accent = accent
        self.ember = ember
        self._key = None
        self.w = self.h = 0

    def ensure(self, w, h, seed):
        if self._key != (w, h, seed):
            self.w, self.h = w, h
            self.rng = random.Random(seed)
            self.build(w, h, self.rng)
            self._key = (w, h, seed)

    def build(self, w, h, rng):
        pass

    def paint(self, p: QPainter, t: float):
        raise NotImplementedError

    # shared particle field: x,y in 0..1, drifting with wrap-around
    def make_particles(self, rng, n, speed=(0.002, 0.005), size=(1.0, 2.6)):
        return [{"x": rng.random(), "y": rng.random(),
                 "v": speed[0] + rng.random() * (speed[1] - speed[0]),
                 "s": size[0] + rng.random() * (size[1] - size[0]),
                 "ph": rng.random() * 6.28, "dr": 0.5 + rng.random()} for _ in range(n)]

    @staticmethod
    def particle_pos(pt, t, direction=-1, sway=0.012):
        y = (pt["y"] + direction * pt["v"] * t * 25) % 1.2 - 0.1
        x = (pt["x"] + math.sin(t * pt["dr"] + pt["ph"]) * sway) % 1.0
        return x, y


# -- RuneScape: Dragonwilds - the original moonlit ridges and rising embers ----------

class DragonwildsScene(Scene):
    def build(self, w, h, rng):
        self.hue = QColor(self.accent).hueF()
        self.ridges = []
        for layer in range(4):
            pts = []
            base = 0.30 + layer * 0.17
            rough = 0.05 + layer * 0.05
            steps = 7 + layer * 3
            for i in range(steps + 1):
                x = i / steps
                y = base + (rng.random() - 0.5) * rough * 2 \
                    + math.sin(x * math.pi * (1 + layer)) * 0.03 * (rng.random() + 0.4)
                pts.append(QPointF(x * w, y * h))
            self.ridges.append(pts)
        self.moon = (0.18 + rng.random() * 0.64, 0.26 + rng.random() * 0.18,
                     20.0 + rng.random() * 12.0)
        self.embers = self.make_particles(rng, 16, (0.0016, 0.005), (1.0, 3.2))

    def paint(self, p, t):
        w, h, hue = self.w, self.h, self.hue
        vgrad(p, QRectF(0, 0, w, h), [(0, QColor.fromHsvF(hue, 0.55, 0.20)),
                                      (0.55, QColor.fromHsvF((hue + 0.03) % 1, 0.5, 0.09)),
                                      (1, QColor("#070A0E"))])
        mx, my, mr = self.moon
        halo = QColor.fromHsvF(hue, 0.30, 1.0)
        halo.setAlphaF(0.28)
        glow(p, mx * w, my * h, mr * 3.2, halo)
        p.setBrush(QColor.fromHsvF(hue, 0.12, 0.98))
        p.drawEllipse(QPointF(mx * w, my * h), mr, mr)
        for i, pts in enumerate(self.ridges):
            k = i / 3
            fill_ridge(p, pts, h, QColor.fromHsvF(hue, 0.42 * (1 - k), 0.16 * (1 - k) + 0.03))
        ember = QColor(self.ember).lighter(125)
        for em in self.embers:
            x, y = self.particle_pos(em, t)
            if y < 0.35:
                continue
            a = max(0.0, min(0.8, (y - 0.35) * 1.1)) * (0.6 + 0.4 * math.sin(t * 2 + em["ph"]))
            p.setBrush(col(ember.name(), a))
            p.drawEllipse(QPointF(x * w, y * h), em["s"] * 0.7, em["s"] * 0.7)


# -- Valheim - aurora, snowy peaks, a pine-black shoreline ------------------------------

class ValheimScene(Scene):
    def build(self, w, h, rng):
        self.stars = [(rng.random() * w, rng.random() * h * 0.55, rng.random()) for _ in range(70)]
        self.peaks = [ridge(rng, w, h, 0.42 + i * 0.12, 0.10 - i * 0.02, 6 + i * 3, 0.02)
                      for i in range(3)]
        self.pines = []
        x = -10
        while x < w + 10:
            ph = h * (0.18 + rng.random() * 0.16)
            self.pines.append((x, ph, 8 + rng.random() * 8))
            x += 7 + rng.random() * 9
        self.snow = self.make_particles(rng, 40, (0.001, 0.003), (0.8, 2.0))
        self.phase = rng.random() * 6.28

    def paint(self, p, t):
        w, h = self.w, self.h
        vgrad(p, QRectF(0, 0, w, h), [(0, "#050A16"), (0.6, "#0B1A26"), (1, "#0A1218")])
        for sx, sy, tw in self.stars:
            a = 0.25 + 0.55 * (0.5 + 0.5 * math.sin(t * (1 + tw * 2) + tw * 9))
            p.setPen(Qt.NoPen)
            p.setBrush(col("#DDEBFF", a * 0.8))
            p.drawEllipse(QPointF(sx, sy), 0.9, 0.9)
        # aurora: soft ribbons made of vertical gradient strips along a sine path
        for band, (c1, amp, off, yb) in enumerate(((self.accent, 0.10, 0.0, 0.22),
                                                   ("#7CE3FF", 0.07, 1.7, 0.30),
                                                   ("#B48CFF", 0.05, 3.1, 0.18))):
            strips = 70
            for i in range(strips):
                x = i / strips
                y = yb + math.sin(x * 5.0 + t * 0.35 + off + self.phase) * amp \
                    + math.sin(x * 11 + t * 0.6 + off) * 0.015
                top, height = y * h, h * (0.16 + 0.05 * math.sin(x * 7 + t + off))
                g = QLinearGradient(0, top, 0, top + height)
                a = 0.16 + 0.12 * math.sin(x * 9 + t * 0.8 + off)
                g.setColorAt(0.0, col(c1, 0))
                g.setColorAt(0.55, col(c1, a * (0.7 if band else 1.0)))
                g.setColorAt(1.0, col(c1, 0))
                p.fillRect(QRectF(x * w, top, w / strips + 1, height), QBrush(g))
        # mountains with snow caps
        for i, pts in enumerate(self.peaks):
            base = QColor("#1B2E3C").darker(100 + i * 45)
            fill_ridge(p, pts, h, base)
            if i < 2:
                p.save()
                path = QPainterPath()
                path.moveTo(pts[0].x(), h)
                for pt in pts:
                    path.lineTo(pt)
                path.lineTo(pts[-1].x(), h)
                p.setClipPath(path)
                top = min(pt.y() for pt in pts)
                vgrad(p, QRectF(0, top, w, h * 0.12), [(0, col("#E8F4FF", 0.55 - i * 0.2)),
                                                        (1, col("#E8F4FF", 0))])
                p.restore()
        # pine shoreline
        p.setBrush(QColor("#050B0E"))
        p.setPen(Qt.NoPen)
        for x, ph, pw in self.pines:
            base = h + 2
            path = QPainterPath()
            tiers = 4
            for k in range(tiers):
                ty = base - ph * (k / tiers)
                hw = pw * (1 - k / (tiers + 0.6))
                path.moveTo(x - hw, ty)
                path.lineTo(x, ty - ph / tiers * 1.6)
                path.lineTo(x + hw, ty)
                path.closeSubpath()
            p.drawPath(path)
        for s in self.snow:
            x, y = self.particle_pos(s, t, direction=1, sway=0.02)
            p.setBrush(col("#F2F8FF", 0.55))
            p.drawEllipse(QPointF(x * w, y * h), s["s"] * 0.6, s["s"] * 0.6)


# -- Enshrouded - violet shroud rolling around a flame -----------------------------------

class EnshroudedScene(Scene):
    def build(self, w, h, rng):
        self.hills = [smooth_ridge(rng, w, h, 0.55 + i * 0.13, 0.12, 4 + i) for i in range(3)]
        self.tower_x = w * (0.62 + rng.random() * 0.2)
        self.fog = [(rng.random(), 0.45 + rng.random() * 0.45, 60 + rng.random() * 90,
                     rng.random() * 6.28, 0.02 + rng.random() * 0.03) for _ in range(9)]
        self.spores = self.make_particles(rng, 26, (0.001, 0.003), (1.0, 2.4))
        self.flame_x = w * (0.22 + rng.random() * 0.2)

    def paint(self, p, t):
        w, h = self.w, self.h
        vgrad(p, QRectF(0, 0, w, h), [(0, "#120B22"), (0.5, "#2A1238"), (0.8, "#3A1630"),
                                      (1, "#120A14")])
        glow(p, w * 0.75, h * 0.32, w * 0.45, col("#FF7A59", 0.18))
        # ruined tower
        tx, ty = self.tower_x, h * 0.30
        path = QPainterPath()
        path.moveTo(tx - 9, h * 0.62)
        path.lineTo(tx - 7, ty + 10)
        path.lineTo(tx - 3, ty)
        path.lineTo(tx + 1, ty + 6)
        path.lineTo(tx + 5, ty + 2)
        path.lineTo(tx + 8, h * 0.62)
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1A0F24"))
        p.drawPath(path)
        for i, hill in enumerate(self.hills):
            p.setBrush(QColor("#1E1030").darker(100 + i * 60))
            p.drawPath(hill)
        # shroud fog
        for fx, fy, fr, ph, sp in self.fog:
            x = ((fx + t * sp * 0.3) % 1.3 - 0.15) * w
            y = fy * h + math.sin(t * 0.4 + ph) * 6
            glow(p, x, y, fr, col("#B06BFF" if ph > 3 else "#E0457A", 0.22))
        # flame
        fx, fy = self.flame_x, h * 0.66
        flick = 0.8 + 0.2 * math.sin(t * 9) * math.sin(t * 5.3)
        glow(p, fx, fy, 46 * flick, col(self.ember, 0.55))
        glow(p, fx, fy - 4, 12 * flick, col("#FFE2A8", 0.95), core=2.5)
        for s in self.spores:
            x, y = self.particle_pos(s, t)
            a = 0.35 + 0.35 * math.sin(t * 2 + s["ph"])
            p.setBrush(col(self.accent, a))
            p.drawEllipse(QPointF(x * w, y * h), s["s"] * 0.7, s["s"] * 0.7)


# -- Palworld - a bright day with fat clouds and round friends on the hills ----------------

class PalworldScene(Scene):
    def build(self, w, h, rng):
        self.clouds = []
        for _ in range(5):
            cx, cy, scale = rng.random(), 0.12 + rng.random() * 0.25, 0.7 + rng.random() * 0.8
            puffs = [((rng.random() - 0.5) * 50 * scale, (rng.random() - 0.5) * 10 * scale,
                      (10 + rng.random() * 12) * scale) for _ in range(6)]
            self.clouds.append((cx, cy, puffs, 0.004 + rng.random() * 0.006))
        self.hills = [smooth_ridge(rng, w, h, 0.56 + i * 0.13, 0.14, 3 + i) for i in range(3)]
        self.pals = [(0.15 + rng.random() * 0.7, 0.7 + rng.random() * 0.12,
                      7 + rng.random() * 5, rng.random() * 6.28,
                      rng.choice(["#FFE3A3", "#9FE3FF", "#FFB3C8", "#C9F29B"]))
                     for _ in range(3)]

    def paint(self, p, t):
        w, h = self.w, self.h
        vgrad(p, QRectF(0, 0, w, h), [(0, "#2F8DE0"), (0.5, "#6FC3F5"), (1, "#BEE8FF")])
        sx, sy = w * 0.82, h * 0.2
        glow(p, sx, sy, 80, col("#FFF4B8", 0.55))
        p.setBrush(col("#FFF6CC"))
        p.drawEllipse(QPointF(sx, sy), 16, 16)
        p.setPen(Qt.NoPen)
        for cx, cy, puffs, sp in self.clouds:
            x0 = ((cx + t * sp) % 1.3 - 0.15) * w
            for dx, dy, r in puffs:
                p.setBrush(col("#FFFFFF", 0.92))
                p.drawEllipse(QPointF(x0 + dx, cy * h + dy), r, r)
        greens = ["#7DD36B", "#4EB45A", "#2E8E4C"]
        for i, hill in enumerate(self.hills):
            p.setBrush(QColor(greens[i]))
            p.drawPath(hill)
        for px, py, r, ph, c in self.pals:
            hop = abs(math.sin(t * 2.2 + ph)) * 5
            x, y = px * w, py * h - hop
            p.setBrush(col("#000000", 0.18))
            p.drawEllipse(QPointF(x, py * h + r * 0.9), r * 0.9, r * 0.25)
            p.setBrush(QColor(c))
            p.drawEllipse(QPointF(x, y), r, r * 0.92)
            ear = QPainterPath()
            ear.moveTo(x - r * 0.7, y - r * 0.4)
            ear.lineTo(x - r * 0.45, y - r * 1.35)
            ear.lineTo(x - r * 0.1, y - r * 0.7)
            ear.moveTo(x + r * 0.7, y - r * 0.4)
            ear.lineTo(x + r * 0.45, y - r * 1.35)
            ear.lineTo(x + r * 0.1, y - r * 0.7)
            p.drawPath(ear)
            p.setBrush(QColor("#2A2A2A"))
            p.drawEllipse(QPointF(x - r * 0.33, y - r * 0.05), r * 0.12, r * 0.15)
            p.drawEllipse(QPointF(x + r * 0.33, y - r * 0.05), r * 0.12, r * 0.15)


# -- Core Keeper - a pixel-art cave around the glowing Core --------------------------------

class CoreKeeperScene(Scene):
    CELL = 5

    def build(self, w, h, rng):
        cw, ch = max(1, w // self.CELL), max(1, h // self.CELL)
        img = QImage(cw, ch, QImage.Format_RGB32)
        rock = [QColor("#151820"), QColor("#1C2029"), QColor("#232836"), QColor("#2B3142")]
        cx, cy = cw * 0.5, ch * 0.48
        for y in range(ch):
            for x in range(cw):
                # a cavern: open (dark) near the middle, rock towards the edges
                dx, dy = (x - cx) / (cw * 0.55), (y - cy) / (ch * 0.62)
                d = dx * dx + dy * dy + (rng.random() - 0.5) * 0.18
                if d < 0.55:
                    c = QColor("#0B0D12") if (x + y) % 2 else QColor("#0D1016")
                else:
                    c = rock[min(3, int((d - 0.55) * 5 + rng.random() * 1.5))]
                img.setPixelColor(x, y, c)
        # ore veins
        self.ores = []
        for _ in range(14):
            x, y = rng.randrange(cw), rng.randrange(ch)
            dx, dy = (x - cx) / (cw * 0.55), (y - cy) / (ch * 0.62)
            if dx * dx + dy * dy > 0.6:
                c = rng.choice(["#E3A54D", "#5FE3F2", "#B87CF0"])
                img.setPixelColor(x, y, QColor(c))
                self.ores.append((x, y, c, rng.random() * 6.28))
        self.base = QPixmap.fromImage(img.scaled(cw * self.CELL, ch * self.CELL,
                                                 Qt.IgnoreAspectRatio, Qt.FastTransformation))
        self.core = (cx * self.CELL, cy * self.CELL)
        self.torches = [(w * 0.18, h * 0.55), (w * 0.82, h * 0.5)]

    def paint(self, p, t):
        p.drawPixmap(0, 0, self.base)
        cx, cy = self.core
        pulse = 0.75 + 0.25 * math.sin(t * 1.6)
        glow(p, cx, cy, 120 * pulse, col(self.accent, 0.35))
        # the Core: a blocky crystal, drawn on the pixel grid
        c = self.CELL
        p.setPen(Qt.NoPen)
        shape = [(0, -4), (-1, -3), (0, -3), (1, -3), (-2, -2), (-1, -2), (0, -2), (1, -2),
                 (2, -2), (-2, -1), (-1, -1), (0, -1), (1, -1), (2, -1), (-1, 0), (0, 0),
                 (1, 0), (0, 1)]
        for dx, dy in shape:
            shade_ = "#D8FBFF" if dx <= 0 and dy < -1 else self.accent
            p.setBrush(QColor(shade_))
            p.drawRect(QRectF(cx + dx * c - c / 2, cy + dy * c, c, c))
        # pedestal
        p.setBrush(QColor("#3A4152"))
        p.drawRect(QRectF(cx - 3 * c - c / 2, cy + 2 * c, 7 * c, c * 2))
        for tx, ty in self.torches:
            fl = 0.7 + 0.3 * math.sin(t * 11 + tx)
            glow(p, tx, ty, 40 * fl, col(self.ember, 0.45))
            p.setBrush(QColor("#6B4A2A"))
            p.drawRect(QRectF(tx - c / 2, ty, c, c * 3))
            p.setBrush(QColor("#FFD27A"))
            p.drawRect(QRectF(tx - c / 2, ty - c, c, c))
        for x, y, oc, ph in self.ores:
            if math.sin(t * 2 + ph) > 0.85:
                p.setBrush(col("#FFFFFF", 0.9))
                p.drawRect(QRectF(x * c + 1, y * c + 1, c - 2, c - 2))


# -- Sons of the Forest - pine trunks in the fog, a far fire ------------------------------

class SonsScene(Scene):
    def build(self, w, h, rng):
        self.layers = []
        for depth in range(4):
            trunks = []
            x = -20
            while x < w + 20:
                tw = (3 + depth * 3.5) * (0.7 + rng.random() * 0.6)
                trunks.append((x, tw, rng.random() * 0.1))
                x += tw + 6 + rng.random() * (40 - depth * 7)
            self.layers.append(trunks)
        self.leaves = self.make_particles(rng, 18, (0.001, 0.0025), (1.2, 2.8))
        self.fire_x = w * (0.3 + rng.random() * 0.4)

    def paint(self, p, t):
        w, h = self.w, self.h
        vgrad(p, QRectF(0, 0, w, h), [(0, "#1B201C"), (0.6, "#262B24"), (1, "#0C0E0C")])
        flick = 0.85 + 0.15 * math.sin(t * 7) * math.sin(t * 3.1)
        glow(p, self.fire_x, h * 0.78, 90 * flick, col(self.accent, 0.35))
        p.setPen(Qt.NoPen)
        for depth, trunks in enumerate(self.layers):
            shade_ = 0.32 - depth * 0.085
            c = QColor.fromHsvF(0.28, 0.18, max(0.02, shade_ * 0.55))
            for x, tw, lean in trunks:
                path = QPainterPath()
                path.moveTo(x, h)
                path.lineTo(x + lean * 30, 0)
                path.lineTo(x + lean * 30 + tw * 0.8, 0)
                path.lineTo(x + tw, h)
                path.closeSubpath()
                p.setBrush(c)
                p.drawPath(path)
            # fog band between depths
            y = h * (0.55 + depth * 0.1) + math.sin(t * 0.3 + depth) * 4
            vgrad(p, QRectF(0, y - 18, w, 36), [(0, col("#9AA59A", 0)),
                                                (0.5, col("#9AA59A", 0.10)),
                                                (1, col("#9AA59A", 0))])
        for lf in self.leaves:
            x, y = self.particle_pos(lf, t, direction=1, sway=0.04)
            p.save()
            p.translate(x * w, y * h)
            p.rotate((t * 60 + lf["ph"] * 57) % 360)
            p.setBrush(col("#6B5A3A", 0.7))
            p.drawEllipse(QPointF(0, 0), lf["s"] * 1.4, lf["s"] * 0.6)
            p.restore()


# -- V Rising - blood moon, castle spires, bats -----------------------------------------------

class VRisingScene(Scene):
    def build(self, w, h, rng):
        self.moon = (w * (0.62 + rng.random() * 0.18), h * 0.34, 34 + rng.random() * 10)
        self.craters = [((rng.random() - 0.5) * 1.2, (rng.random() - 0.5) * 1.2,
                         0.08 + rng.random() * 0.14) for _ in range(6)]
        self.cliff = ridge(rng, w, h, 0.66, 0.08, 9, 0.04)
        self.castle_x = w * (0.18 + rng.random() * 0.15)
        self.towers = [(dx, 22 + rng.random() * 30, 6 + rng.random() * 5)
                       for dx in (-34, -18, -4, 12, 28)]
        self.bats = [(rng.random(), 0.15 + rng.random() * 0.35, 0.02 + rng.random() * 0.03,
                      rng.random() * 6.28, 3 + rng.random() * 3) for _ in range(7)]
        self.mist = ridge(rng, w, h, 0.8, 0.04, 6, 0.02)

    def paint(self, p, t):
        w, h = self.w, self.h
        vgrad(p, QRectF(0, 0, w, h), [(0, "#14061A"), (0.55, "#2E0B24"), (1, "#0E060C")])
        mx, my, mr = self.moon
        glow(p, mx, my, mr * 3.4, col(self.accent, 0.35))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#C8283F"))
        p.drawEllipse(QPointF(mx, my), mr, mr)
        for cx, cy, cr in self.craters:
            p.setBrush(col("#7E1428", 0.45))
            p.drawEllipse(QPointF(mx + cx * mr * 0.7, my + cy * mr * 0.7), cr * mr, cr * mr)
        fill_ridge(p, self.cliff, h, QColor("#0A0409"))
        # castle
        bx = self.castle_x
        base_y = min(pt.y() for pt in self.cliff) + 6
        p.setBrush(QColor("#0A0409"))
        p.drawRect(QRectF(bx - 40, base_y - 18, 80, 30))
        for dx, th, tw in self.towers:
            x = bx + dx
            p.drawRect(QRectF(x - tw / 2, base_y - 18 - th, tw, th + 2))
            spire = QPainterPath()
            spire.moveTo(x - tw / 2 - 1, base_y - 18 - th)
            spire.lineTo(x, base_y - 18 - th - tw * 2.2)
            spire.lineTo(x + tw / 2 + 1, base_y - 18 - th)
            spire.closeSubpath()
            p.drawPath(spire)
            if math.sin(t * 0.7 + dx) > -0.2:
                p.setBrush(col("#FF4D5E", 0.85))
                p.drawRect(QRectF(x - 1, base_y - 18 - th * 0.6, 2, 3))
                p.setBrush(QColor("#0A0409"))
        for bx0, by, sp, ph, size in self.bats:
            x = ((bx0 + t * sp) % 1.2 - 0.1) * w
            y = by * h + math.sin(t * 1.3 + ph) * 8
            flap = math.sin(t * 14 + ph) * size * 0.8
            path = QPainterPath()
            path.moveTo(x - size * 1.8, y - flap)
            path.quadTo(x - size * 0.7, y - size * 0.2, x, y)
            path.quadTo(x + size * 0.7, y - size * 0.2, x + size * 1.8, y - flap)
            path.quadTo(x + size * 0.6, y + size * 0.4, x, y + size * 0.3)
            path.quadTo(x - size * 0.6, y + size * 0.4, x - size * 1.8, y - flap)
            p.setBrush(QColor("#050205"))
            p.drawPath(path)
        fill_ridge(p, self.mist, h, col("#3A0F2A", 0.5))


# -- Grounded - the backyard from ant height ------------------------------------------------

class GroundedScene(Scene):
    def build(self, w, h, rng):
        self.blades = []
        for _ in range(42):
            depth = rng.random()
            self.blades.append((rng.random() * w, h * (0.25 + (1 - depth) * 0.45),
                                3 + depth * 9, depth, (rng.random() - 0.5) * 0.5,
                                rng.random() * 6.28))
        self.blades.sort(key=lambda b: b[3])
        self.bokeh = [(rng.random() * w, rng.random() * h * 0.6, 8 + rng.random() * 26,
                       rng.random() * 6.28) for _ in range(12)]
        self.dew = [(rng.randrange(len(self.blades)), 0.3 + rng.random() * 0.4)
                    for _ in range(5)]
        self.seed = self.make_particles(rng, 3, (0.0006, 0.0012), (2.0, 3.0))

    def paint(self, p, t):
        w, h = self.w, self.h
        vgrad(p, QRectF(0, 0, w, h), [(0, "#BFE6A2"), (0.45, "#7CC46A"), (1, "#1E3F1A")])
        sx, sy = w * 0.25, h * 0.15
        glow(p, sx, sy, 160, col("#FFF3B0", 0.65))
        for bx, by, br, ph in self.bokeh:
            a = 0.10 + 0.08 * math.sin(t * 0.8 + ph)
            p.setPen(Qt.NoPen)
            p.setBrush(col("#FFFBE0", a))
            p.drawEllipse(QPointF(bx, by), br, br)
        tips = []
        for x, height, width, depth, lean, ph in self.blades:
            sway = math.sin(t * 1.1 + ph) * (4 + depth * 6)
            top_x = x + lean * height + sway
            top_y = h - height * (0.9 + depth * 0.9)
            path = QPainterPath()
            path.moveTo(x - width / 2, h + 2)
            path.quadTo(x - width / 3 + sway * 0.3, h - height * 0.6, top_x, top_y)
            path.quadTo(x + width / 3 + sway * 0.3, h - height * 0.6, x + width / 2, h + 2)
            path.closeSubpath()
            g = QLinearGradient(0, top_y, 0, h)
            base = QColor.fromHsvF(0.27 + depth * 0.03, 0.55 + depth * 0.2, 0.75 - depth * 0.5)
            g.setColorAt(0, base.lighter(135))
            g.setColorAt(1, base.darker(160))
            p.setBrush(QBrush(g))
            p.drawPath(path)
            tips.append((top_x, top_y, x, h))
        for idx, k in self.dew:
            tx, ty, bx, by = tips[idx]
            x, y = tx + (bx - tx) * k, ty + (by - ty) * k
            glint = 0.6 + 0.4 * math.sin(t * 3 + idx)
            p.setBrush(col("#E8FFF6", 0.55))
            p.drawEllipse(QPointF(x, y), 3.2, 3.2)
            p.setBrush(col("#FFFFFF", glint))
            p.drawEllipse(QPointF(x - 1, y - 1), 1.1, 1.1)
        p.setPen(QPen(col("#FFFFFF", 0.7), 0.8))
        for s in self.seed:
            x, y = self.particle_pos(s, t, sway=0.05)
            cx, cy = x * w, y * h
            for k in range(8):
                ang = k * math.pi / 4 + t * 0.4
                p.drawLine(QPointF(cx, cy),
                           QPointF(cx + math.cos(ang) * 6, cy + math.sin(ang) * 6))
        p.setPen(Qt.NoPen)


# -- Raft - sunset over open water, a raft and a fin ------------------------------------------

class RaftScene(Scene):
    def build(self, w, h, rng):
        self.horizon = h * 0.58
        self.sun_x = w * (0.55 + rng.random() * 0.3)
        self.waves = [(0.0 + i * 0.1, 0.8 + i * 0.6, rng.random() * 6.28) for i in range(5)]
        self.raft_x = w * (0.18 + rng.random() * 0.2)
        self.gulls = [(rng.random(), 0.12 + rng.random() * 0.2, rng.random() * 6.28)
                      for _ in range(3)]

    def paint(self, p, t):
        w, h, hz = self.w, self.h, self.horizon
        vgrad(p, QRectF(0, 0, w, hz), [(0, "#1B2550"), (0.45, "#8A3F6E"), (0.8, "#F07A5A"),
                                       (1, "#FFC07A")])
        glow(p, self.sun_x, hz, 110, col("#FFD58A", 0.6))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFE2A6"))
        p.drawPie(QRectF(self.sun_x - 24, hz - 24, 48, 48), 0, 180 * 16)
        vgrad(p, QRectF(0, hz, w, h - hz), [(0, "#2A6F8F"), (1, "#062030")])
        for i in range(10):     # sun reflection streaks
            y = hz + 4 + i * 6
            half = (26 - i * 2) * (0.8 + 0.2 * math.sin(t * 2 + i))
            p.setBrush(col("#FFD08A", 0.55 - i * 0.05))
            p.drawRect(QRectF(self.sun_x - half, y, half * 2, 1.6))
        for i, (depth, speed, ph) in enumerate(self.waves):
            y0 = hz + (h - hz) * (0.15 + depth * 1.6)
            path = QPainterPath()
            path.moveTo(0, h)
            for k in range(41):
                x = k / 40 * w
                y = y0 + math.sin(k * 0.6 + t * speed + ph) * (2 + i)
                path.lineTo(x, y)
            path.lineTo(w, h)
            path.closeSubpath()
            p.setBrush(col("#0B3A52", 0.35 + i * 0.1))
            p.drawPath(path)
        # raft
        bob = math.sin(t * 1.4) * 2
        rx, ry = self.raft_x, hz + (h - hz) * 0.42 + bob
        p.setBrush(QColor("#5A3A22"))
        p.drawRect(QRectF(rx - 18, ry, 36, 5))
        p.setBrush(QColor("#3A2616"))
        p.drawRect(QRectF(rx - 1, ry - 26, 2, 26))
        sail = QPainterPath()
        sail.moveTo(rx + 1, ry - 25)
        sail.lineTo(rx + 16, ry - 8)
        sail.lineTo(rx + 1, ry - 6)
        sail.closeSubpath()
        p.setBrush(QColor("#E8D8B8"))
        p.drawPath(sail)
        # shark fin circling
        ang = t * 0.5
        fx = rx + math.cos(ang) * 70
        fy = ry + 14 + math.sin(ang) * 10
        fin = QPainterPath()
        fin.moveTo(fx - 7, fy)
        fin.quadTo(fx - 1, fy - 6, fx + 2, fy - 13)
        fin.quadTo(fx + 3, fy - 5, fx + 7, fy)
        fin.closeSubpath()
        p.setBrush(QColor("#1C2C36"))
        p.drawPath(fin)
        p.setPen(QPen(col("#2A1A2A", 0.8), 1.2))
        for gx, gy, ph in self.gulls:
            x = ((gx + t * 0.01) % 1.1) * w
            y = gy * h + math.sin(t + ph) * 4
            flap = math.sin(t * 6 + ph) * 2.5
            p.drawLine(QPointF(x - 6, y - flap), QPointF(x, y))
            p.drawLine(QPointF(x, y), QPointF(x + 6, y - flap))
        p.setPen(Qt.NoPen)


# -- 7 Days to Die - a ruined skyline under a red sky ----------------------------------------

class SevenDaysScene(Scene):
    def build(self, w, h, rng):
        self.buildings = []
        x = -5
        while x < w + 5:
            bw = 18 + rng.random() * 34
            bh = h * (0.18 + rng.random() * 0.36)
            broken = [(rng.random(), rng.random() * 0.25) for _ in range(3)]
            windows = [(rng.random(), rng.random(), rng.random() * 6.28) for _ in range(5)]
            self.buildings.append((x, bw, bh, broken, windows))
            x += bw + rng.random() * 6
        self.moon = (w * (0.15 + rng.random() * 0.7), h * 0.26, 20 + rng.random() * 8)
        self.ash = self.make_particles(rng, 36, (0.001, 0.003), (0.8, 1.8))
        self.walkers = [(rng.random(), 0.004 + rng.random() * 0.004, rng.random() * 6.28)
                        for _ in range(4)]
        self.poles = [w * (0.1 + i * 0.27 + rng.random() * 0.05) for i in range(4)]

    def paint(self, p, t):
        w, h = self.w, self.h
        vgrad(p, QRectF(0, 0, w, h), [(0, "#2A0A08"), (0.5, "#7A2414"), (0.8, "#B8481E"),
                                      (1, "#2A120A")])
        mx, my, mr = self.moon
        glow(p, mx, my, mr * 4, col("#FF5A3A", 0.4))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E0432A"))
        p.drawEllipse(QPointF(mx, my), mr, mr)
        ground = h * 0.86
        for x, bw, bh, broken, windows in self.buildings:
            top = ground - bh
            path = QPainterPath()
            path.moveTo(x, ground)
            path.lineTo(x, top + broken[0][1] * bh)
            path.lineTo(x + bw * broken[1][0] * 0.5, top + broken[1][1] * bh)
            path.lineTo(x + bw * (0.5 + broken[2][0] * 0.5), top + broken[2][1] * bh * 0.4)
            path.lineTo(x + bw, top + broken[0][1] * bh * 0.6)
            path.lineTo(x + bw, ground)
            path.closeSubpath()
            p.setBrush(QColor("#1A0B07"))
            p.drawPath(path)
            for wx, wy, ph in windows:
                if math.sin(t * 0.9 + ph) > 0.3:
                    p.setBrush(col("#FFB347", 0.75))
                    p.drawRect(QRectF(x + 3 + wx * (bw - 8), top + bh * 0.3 + wy * bh * 0.6, 3, 4))
        p.setPen(QPen(QColor("#120604"), 1.2))
        for i, px in enumerate(self.poles):
            p.drawLine(QPointF(px, ground), QPointF(px, ground - h * 0.32))
            p.drawLine(QPointF(px - 8, ground - h * 0.3), QPointF(px + 8, ground - h * 0.3))
            if i + 1 < len(self.poles):
                nx = self.poles[i + 1]
                wire = QPainterPath()
                wire.moveTo(px, ground - h * 0.3)
                wire.quadTo((px + nx) / 2, ground - h * 0.22, nx, ground - h * 0.3)
                p.setBrush(Qt.NoBrush)
                p.drawPath(wire)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#0E0503"))
        p.drawRect(QRectF(0, ground, w, h - ground))
        for wx0, sp, ph in self.walkers:
            x = ((wx0 + t * sp) % 1.1 - 0.05) * w
            y = ground
            lurch = math.sin(t * 3 + ph) * 1.5
            p.setBrush(QColor("#080302"))
            p.drawEllipse(QPointF(x + lurch, y - 15), 2.6, 2.8)
            p.drawRect(QRectF(x - 2 + lurch * 0.5, y - 12, 4, 8))
            p.drawRect(QRectF(x - 2, y - 4, 1.5, 4))
            p.drawRect(QRectF(x + 0.5, y - 4, 1.5, 4))
            p.drawRect(QRectF(x + 1 + lurch * 0.5, y - 11, 6, 1.5))
        for a in self.ash:
            x, y = self.particle_pos(a, t, direction=1, sway=0.03)
            p.setBrush(col("#CFC2B8", 0.45))
            p.drawEllipse(QPointF(x * w, y * h), a["s"] * 0.6, a["s"] * 0.6)


# -- WorldSync library - a slowly turning globe, friends in orbit ---------------------------

class LibraryScene(Scene):
    def build(self, w, h, rng):
        self.stars = [(rng.random() * w, rng.random() * h, rng.random()) for _ in range(90)]
        self.nodes = [(rng.random() * 6.28, 0.55 + rng.random() * 0.5, 0.15 + rng.random() * 0.25,
                       rng.choice([self.accent, "#5CD6C9", self.ember, "#F27BA8"]))
                      for _ in range(6)]

    def paint(self, p, t):
        w, h = self.w, self.h
        vgrad(p, QRectF(0, 0, w, h), [(0, "#0B1030"), (0.6, "#0A0E22"), (1, "#080A14")])
        for sx, sy, tw in self.stars:
            a = 0.2 + 0.5 * (0.5 + 0.5 * math.sin(t * (0.7 + tw) + tw * 11))
            p.setPen(Qt.NoPen)
            p.setBrush(col("#DCE4FF", a))
            p.drawEllipse(QPointF(sx, sy), 0.8, 0.8)
        cx, cy, r = w * 0.5, h * 0.62, min(w, h) * 0.42
        glow(p, cx, cy, r * 1.9, col(self.accent, 0.20))
        p.setBrush(col("#10183A", 0.95))
        p.drawEllipse(QPointF(cx, cy), r, r)
        pen = QPen(col(self.accent, 0.35), 1.0)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        for k in range(1, 6):          # latitudes
            yy = cy + r * math.cos(k * math.pi / 6)
            rx = r * math.sin(k * math.pi / 6)
            p.drawEllipse(QPointF(cx, yy), rx, rx * 0.18)
        for k in range(6):              # longitudes, turning
            ang = (k / 6) * math.pi + t * 0.15
            rx = abs(math.cos(ang)) * r
            p.setPen(QPen(col(self.accent, 0.12 + 0.3 * abs(math.cos(ang))), 1.0))
            p.drawEllipse(QPointF(cx, cy), rx, r)
        # orbiting friends, linked to each other by faint arcs
        pts = []
        for ph, rad, speed, c in self.nodes:
            ang = ph + t * speed
            x = cx + math.cos(ang) * r * rad * 1.6
            y = cy - r * 0.2 + math.sin(ang) * r * rad * 0.45
            pts.append((x, y, c, math.sin(ang)))
        p.setPen(QPen(col(self.accent, 0.25), 1.0))
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            path = QPainterPath()
            path.moveTo(a[0], a[1])
            path.quadTo((a[0] + b[0]) / 2, min(a[1], b[1]) - 30, b[0], b[1])
            p.drawPath(path)
        p.setPen(Qt.NoPen)
        for x, y, c, depth in pts:
            size = 2.6 + depth * 1.2
            glow(p, x, y, 12 + depth * 4, col(c, 0.5))
            p.setBrush(QColor(c))
            p.drawEllipse(QPointF(x, y), size, size)


SCENES = {
    "dragonwilds": DragonwildsScene, "valheim": ValheimScene,
    "enshrouded": EnshroudedScene, "palworld": PalworldScene,
    "core_keeper": CoreKeeperScene, "sons_of_the_forest": SonsScene,
    "v_rising": VRisingScene, "grounded": GroundedScene, "raft": RaftScene,
    "seven_days_to_die": SevenDaysScene, "library": LibraryScene,
}


def make(scene_id: str, accent: str, ember: str) -> Scene:
    return SCENES.get(scene_id, LibraryScene)(accent, ember)


def render(scene_id: str, w: int, h: int, accent: str, ember: str,
           seed: int = 7, t: float = 2.5) -> QPixmap:
    """A still frame, for library cards and thumbnails."""
    pm = QPixmap(w, h)
    pm.fill(QColor("#000000"))
    scene = make(scene_id, accent, ember)
    scene.ensure(w, h, seed)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    scene.paint(p, t)
    p.end()
    return pm
