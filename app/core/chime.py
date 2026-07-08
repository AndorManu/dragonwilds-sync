"""A soft ember chime on Play. Pure stdlib (winsound), fail-soft, optional."""

import logging
import sys
from pathlib import Path

log = logging.getLogger("dwsync.chime")


def _asset_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS",
                        Path(__file__).resolve().parent.parent.parent))
    return base / "app" / "assets" / "chime.wav"


def play():
    if sys.platform != "win32":
        return
    path = _asset_path()
    if not path.exists():
        return
    try:
        import winsound
        winsound.PlaySound(str(path),
                           winsound.SND_FILENAME | winsound.SND_ASYNC
                           | winsound.SND_NODEFAULT)
    except Exception:
        log.debug("Chime failed", exc_info=True)
