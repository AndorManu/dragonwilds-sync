"""Inline SVG icon set, rendered to pixmaps at the right DPI and color.

Outline icons are from Feather (MIT); the dragon-eye mark is our own.
"""

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_STROKE_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_ICONS = {
    "play": '<path d="M8 5.2v13.6L19.5 12z" fill="{color}" stroke="none"/>',
    "gear": (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83'
        'l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1'
        '-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0'
        ' 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1'
        'H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.'
        '06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 '
        '0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 '
        '0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.8'
        '2V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
    ),
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "minus": '<path d="M5 12h14"/>',
    "check-circle": (
        '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
        '<polyline points="22 4 12 14.01 9 11.01"/>'
    ),
    "alert": (
        '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3'
        'L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
        '<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'
    ),
    "refresh": (
        '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>'
        '<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>'
    ),
    "folder": (
        '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9'
        'a2 2 0 0 1 2 2z"/>'
    ),
    "download-cloud": (
        '<polyline points="8 17 12 21 16 17"/><line x1="12" y1="12" x2="12" y2="21"/>'
        '<path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"/>'
    ),
    "upload-cloud": (
        '<polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/>'
        '<path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>'
        '<polyline points="16 16 12 12 8 16"/>'
    ),
    "sparkle": (
        '<path d="M12 2.5 13.8 8.7 20 10.5 13.8 12.3 12 18.5 10.2 12.3 4 10.5 '
        '10.2 8.7z" fill="{color}" stroke="none"/>'
        '<path d="M19 15.5l.9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9z" '
        'fill="{color}" stroke="none" opacity="0.55"/>'
    ),
    "chevron-left": '<polyline points="15 18 9 12 15 6"/>',
    "info": (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>'
    ),
    # Our mark: a dragon's eye, calm and watchful.
    "dragon": (
        '<path d="M2.6 12 C 6.8 5.6, 17.2 5.6, 21.4 12 C 17.2 18.4, 6.8 18.4, 2.6 12 Z"/>'
        '<path d="M12 7.6 C 13.1 9, 13.1 15, 12 16.4 C 10.9 15, 10.9 9, 12 7.6 Z" '
        'fill="{color}" stroke="none"/>'
    ),
    "external": (
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
        '<polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>'
    ),
    "user-plus": (
        '<path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
        '<circle cx="8.5" cy="7" r="4"/>'
        '<line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/>'
    ),
    "copy": (
        '<rect x="9" y="9" width="13" height="13" rx="2"/>'
        '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
    ),
    "link": (
        '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
        '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'
    ),
    "archive": (
        '<polyline points="21 8 21 21 3 21 3 8"/>'
        '<rect x="1" y="3" width="22" height="5"/>'
        '<line x1="10" y1="12" x2="14" y2="12"/>'
    ),
    "flag": (
        '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/>'
        '<line x1="4" y1="22" x2="4" y2="15"/>'
    ),
    "clock": (
        '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'
    ),
    "rotate-ccw": (
        '<polyline points="1 4 1 10 7 10"/>'
        '<path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>'
    ),
    "map": (
        '<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/>'
        '<line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>'
    ),
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "trash": (
        '<polyline points="3 6 5 6 21 6"/>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4'
        'a2 2 0 0 1 2 2v2"/>'
    ),
    # -- skill emblems (drawn in-house, gold-line style) ----------------------
    "skill-attack": (
        '<path d="M19.5 4.5 9 15"/><path d="M15.5 3.5l5 5"/>'
        '<path d="M7.5 13.5l3 3-3.5 4-2.5-2.5z"/>'
        '<line x1="3.5" y1="20.5" x2="6" y2="18"/>'
    ),
    "skill-magic": (
        '<path d="M4.5 19h15"/>'
        '<path d="M7 19C8.5 14 10.2 8.5 12 4.5 13.8 8.5 15.5 14 17 19"/>'
        '<path d="M12 10.2l.7 1.4 1.4.7-1.4.7-.7 1.4-.7-1.4-1.4-.7 1.4-.7z" '
        'fill="{color}" stroke="none"/>'
    ),
    "skill-ranged": (
        '<path d="M5.5 3c6 4.5 6 13.5 0 18"/>'
        '<line x1="5.5" y1="12" x2="20" y2="12"/>'
        '<polyline points="17 9 20 12 17 15"/>'
    ),
    "skill-mining": (
        '<path d="M4 10C8 5.2 16 5.2 20 10"/>'
        '<line x1="12" y1="6.6" x2="12" y2="8.5"/>'
        '<line x1="12" y1="8.5" x2="6" y2="20.5"/>'
    ),
    "skill-woodcutting": (
        '<path d="M12 3l4.5 6h-2.5l3.5 5H6.5L10 9H7.5z" fill="{color}" stroke="none"/>'
        '<line x1="12" y1="14" x2="12" y2="20.5"/>'
        '<line x1="9" y1="20.5" x2="15" y2="20.5"/>'
    ),
    "skill-artisan": (
        '<path d="M5 20.5l7-7"/><path d="M10.5 6.5 14 3l5 5-3.5 3.5z"/>'
        '<line x1="19" y1="20.5" x2="13.5" y2="15"/>'
    ),
    "skill-construction": (
        '<rect x="3" y="7" width="18" height="13" rx="1"/>'
        '<line x1="3" y1="13.5" x2="21" y2="13.5"/>'
        '<line x1="9.5" y1="7" x2="9.5" y2="13.5"/>'
        '<line x1="14.5" y1="13.5" x2="14.5" y2="20"/>'
    ),
    "skill-cooking": (
        '<path d="M5.5 10.5h13V13a6.5 6.5 0 0 1-13 0z"/>'
        '<line x1="3.5" y1="10.5" x2="20.5" y2="10.5"/>'
        '<path d="M9.5 7.5c0-1.2 1-1.4 1-2.6M14 7.5c0-1.2 1-1.4 1-2.6"/>'
    ),
    "skill-farming": (
        '<path d="M7.5 10h8.5v7a3 3 0 0 1-3 3h-2.5a3 3 0 0 1-3-3z"/>'
        '<path d="M8.5 10c0-2.3 1.4-3.8 3.2-3.8S15 7.7 15 10"/>'
        '<path d="M16 12.5l4-3 1.5 2"/>'
    ),
    "skill-runecrafting": (
        '<path d="M12 2.5 19 12l-7 9.5L5 12z"/>'
        '<path d="M13.5 7.5 10 12h4l-3.5 4.5"/>'
    ),
    "skill-fishing": (
        '<path d="M6.5 12S10 7 14.5 7c3 0 5.5 3 6.5 5-1 2-3.5 5-6.5 5-4.5 0-8-5-8-5z"/>'
        '<path d="M6.5 12 3 9v6z" fill="{color}" stroke="none"/>'
        '<circle cx="16.5" cy="10.8" r="0.9" fill="{color}" stroke="none"/>'
    ),
    "bell": (
        '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>'
        '<path d="M13.73 21a2 2 0 0 1-3.46 0"/>'
    ),
    "send": (
        '<line x1="22" y1="2" x2="11" y2="13"/>'
        '<polygon points="22 2 15 22 11 13 2 9 22 2"/>'
    ),
    "rocket": (
        '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91'
        'a2.18 2.18 0 0 0-2.91-.09z"/>'
        '<path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 '
        '7.5-6 11a22.35 22.35 0 0 1-4 2z"/>'
        '<path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/>'
        '<path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>'
    ),
}


# Gradient version of the eye for hero moments (welcome screen).
MARK_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="fire" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#4ADD9B"/>
      <stop offset="100%" stop-color="#1FA89B"/>
    </linearGradient>
    <linearGradient id="slit" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#5BE7AC"/>
      <stop offset="100%" stop-color="#1FA89B"/>
    </linearGradient>
  </defs>
  <path d="M 6 32 C 15 17.5, 49 17.5, 58 32 C 49 46.5, 15 46.5, 6 32 Z"
        fill="#3ECF8E" fill-opacity="0.08"
        stroke="url(#fire)" stroke-width="3.2" stroke-linejoin="round"/>
  <path d="M 32 20.5 C 35.8 25, 35.8 39, 32 43.5 C 28.2 39, 28.2 25, 32 20.5 Z"
        fill="url(#slit)"/>
  <circle cx="35" cy="25.5" r="2.2" fill="#EAFBF2" fill-opacity="0.9"/>
</svg>
"""


def mark_pixmap(size: int, dpr: float = 2.0) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(MARK_SVG.encode()))
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size * dpr, size * dpr))
    painter.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def skill_icon_name(label: str) -> str:
    """Icon key for a skill label; falls back to the sparkle."""
    key = f"skill-{(label or '').lower()}"
    return key if key in _ICONS else "sparkle"


def svg_source(name: str, color: str) -> str:
    body = _ICONS[name].format(color=color)
    return _STROKE_TEMPLATE.format(color=color, body=body)


def pixmap(name: str, color: str, size: int, dpr: float = 2.0) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg_source(name, color).encode()))
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size * dpr, size * dpr))
    painter.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name: str, color: str, size: int = 18) -> QIcon:
    return QIcon(pixmap(name, color, size))
