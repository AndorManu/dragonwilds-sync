"""File logging so problems can be diagnosed without a console window."""

import logging
import sys
from logging.handlers import RotatingFileHandler

from . import paths

LOG_FILE = paths.LOG_DIR / "dragonwilds-sync.log"


def setup_logging():
    paths.LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("dwsync")
    root.setLevel(logging.INFO)
    if root.handlers:
        return root

    handler = RotatingFileHandler(LOG_FILE, maxBytes=512 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root.addHandler(handler)

    if sys.stderr is not None:  # visible when run from source; absent in the windowed exe
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)-7s %(name)s: %(message)s"))
        root.addHandler(console)

    def excepthook(exc_type, exc, tb):
        root.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = excepthook
    return root
