"""Launch-with-Windows toggle via the per-user Run registry key.

Only offered in the packaged exe — pointing the Run key at a dev venv would
break the moment the folder moves.
"""

import logging
import sys

log = logging.getLogger("dwsync.autostart")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "DragonwildsSync"

try:
    import winreg
except ImportError:
    winreg = None


def available() -> bool:
    return winreg is not None and getattr(sys, "frozen", False)


def is_enabled() -> bool:
    if not winreg:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(enable: bool) -> bool:
    if not available():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            if enable:
                winreg.SetValueEx(k, VALUE_NAME, 0, winreg.REG_SZ,
                                  f'"{sys.executable}" --tray')
            else:
                try:
                    winreg.DeleteValue(k, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        log.warning("Could not update launch-on-startup", exc_info=True)
        return False
