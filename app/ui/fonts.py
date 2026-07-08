"""Bundled display typefaces — the biggest single lever away from system-font
blandness. Cinzel (roman caps) for wordmarks and titles, Cinzel Decorative
for hero world names, EB Garamond for the occasional flavor line.

All three are SIL OFL 1.1 (see app/assets/fonts/), so they ship in the exe.
Falls back to a Windows serif if the files are somehow missing.
"""

import logging
from pathlib import Path

from PySide6.QtGui import QFontDatabase

log = logging.getLogger("dwsync.fonts")

_FONT_FILES = {
    "Cinzel.ttf": "Cinzel",
    "CinzelDecorative-Bold.ttf": "Cinzel Decorative",
    "EBGaramond.ttf": "EB Garamond",
}

# Resolved family names (filled by load()); fallbacks are legible Windows serifs.
DISPLAY = "Constantia"        # titles, section flourishes
DISPLAY_DECO = "Constantia"   # hero world name
VOICE = "Constantia"          # flavor / italic lines
_loaded = False


def _assets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "fonts"


def load():
    """Register the bundled fonts; safe to call once at startup."""
    global DISPLAY, DISPLAY_DECO, VOICE, _loaded
    if _loaded:
        return
    _loaded = True
    folder = _assets_dir()
    resolved = {}
    for filename, expected in _FONT_FILES.items():
        path = folder / filename
        if not path.exists():
            log.warning("Bundled font missing: %s", path)
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id == -1:
            log.warning("Qt refused font: %s", path)
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            resolved[expected] = families[0]
    DISPLAY = resolved.get("Cinzel", DISPLAY)
    DISPLAY_DECO = resolved.get("Cinzel Decorative", DISPLAY_DECO)
    VOICE = resolved.get("EB Garamond", VOICE)
    log.info("Fonts loaded: display=%s deco=%s voice=%s", DISPLAY, DISPLAY_DECO, VOICE)
