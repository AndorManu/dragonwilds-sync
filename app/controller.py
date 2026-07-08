"""Bridges the sync core and the UI: worker threads in, Qt signals out."""

import logging
import threading

from PySide6.QtCore import QObject, QTimer, Signal

from .core import game, storage, sync
from .core.sync import SyncResult

log = logging.getLogger("dwsync.controller")

STATUS_POLL_MS = 20_000


class ErrorSnapshot:
    kind = "error"
    history = None


class Controller(QObject):
    status_checking = Signal()
    status_changed = Signal(object)          # StatusSnapshot | ErrorSnapshot
    phase_changed = Signal(str)              # idle/checking/launching/waiting/ingame/pushing
    toast = Signal(str, str)                 # kind, message
    confirm_requested = Signal(object)       # {"title","body","danger","event","answer"}
    config_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = storage.load_config()
        self.state = storage.load_state()
        self.phase = "idle"
        self._busy = threading.Lock()

        self._poll = QTimer(self)
        self._poll.setInterval(STATUS_POLL_MS)
        self._poll.timeout.connect(lambda: self.refresh_status(silent=True))
        if self.cfg:
            self._poll.start()

    # -- config ----------------------------------------------------------------
    @property
    def has_config(self) -> bool:
        return bool(self.cfg)

    def save_config(self, cfg: dict):
        storage.save_config(cfg)
        self.cfg = cfg
        self.config_changed.emit(cfg)
        self._poll.start()
        self.refresh_status()

    # -- status -------------------------------------------------------------------
    def refresh_status(self, silent=False):
        if not self.cfg:
            return
        if not silent:
            self.status_checking.emit()

        def worker():
            try:
                snapshot = sync.get_status(self.cfg, self.state)
                self.status_changed.emit(snapshot)
            except Exception:
                log.exception("Status check failed")
                self.status_changed.emit(ErrorSnapshot())

        threading.Thread(target=worker, daemon=True, name="status").start()

    # -- helpers used by workers ----------------------------------------------------
    def _set_phase(self, phase):
        self.phase = phase
        self.phase_changed.emit(phase)

    def _confirm(self, title, body, danger="Overwrite") -> bool:
        """Block the worker thread until the UI answers the overlay."""
        request = {"title": title, "body": body, "danger": danger,
                   "event": threading.Event(), "answer": False}
        self.confirm_requested.emit(request)
        request["event"].wait()
        return request["answer"]

    def _log(self, message):
        log.info(message)

    # -- play workflow -------------------------------------------------------------
    def start_play(self):
        if not self._busy.acquire(blocking=False):
            return
        threading.Thread(target=self._play_flow, daemon=True, name="play").start()

    def _play_flow(self):
        try:
            self._set_phase("checking")
            result, self.state = sync.do_pull(self.cfg, self.state, self._log, self._confirm)
            storage.save_state(self.state)
            self.status_changed.emit(sync.get_status(self.cfg, self.state))

            if result == SyncResult.PULLED:
                self.toast.emit("success", "Latest save pulled in — you're starting fresh off "
                                           "your friends' progress.")
            elif result == SyncResult.CONFLICT_CANCELLED:
                self.toast.emit("info", "Kept your local progress. It'll be shared when "
                                        "you finish this session.")
            elif result == SyncResult.MISSING_FILES:
                self.toast.emit("warning", "The newest save hasn't finished syncing to this PC — "
                                           "you're playing your current local copy.")

            if game.find_game_process():
                self.toast.emit("info", "Dragonwilds is already running — I'll share your "
                                        "progress when you close it.")
            else:
                self._set_phase("launching")
                how = game.launch_game(self.cfg)
                log.info("Game launched via %s", how)

            if not game.process_watch_available():
                self._set_phase("idle")
                self.toast.emit("warning", "I can't watch for the game closing on this PC. "
                                           "Hit “Save my progress now” when you're done.")
                return

            self._set_phase("waiting")
            proc = game.find_game_process() or game.wait_for_game_start()
            if proc is None:
                self._set_phase("idle")
                self.toast.emit("warning", "Never saw the game start. If you are playing, use "
                                           "“Save my progress now” when you're done.")
                return

            self._set_phase("ingame")
            game.wait_for_game_exit(proc)

            self._set_phase("pushing")
            result, self.state = sync.do_push(self.cfg, self.state, self._log, self._confirm)
            storage.save_state(self.state)
            self._after_push(result)
        except Exception:
            log.exception("Play flow failed")
            self.toast.emit("error", "Something went wrong during the session. Your save is "
                                     "still on this PC — try “Save my progress now”.")
        finally:
            self._set_phase("idle")
            self.status_changed.emit(self._safe_status())
            self._busy.release()

    # -- manual push ------------------------------------------------------------------
    def push_now(self):
        if not self._busy.acquire(blocking=False):
            return
        threading.Thread(target=self._push_flow, daemon=True, name="push").start()

    def _push_flow(self):
        try:
            self._set_phase("pushing")
            result, self.state = sync.do_push(self.cfg, self.state, self._log, self._confirm)
            storage.save_state(self.state)
            self._after_push(result)
        except Exception:
            log.exception("Manual push failed")
            self.toast.emit("error", "Couldn't share your save. Check that your cloud folder "
                                     "is reachable, then try again.")
        finally:
            self._set_phase("idle")
            self.status_changed.emit(self._safe_status())
            self._busy.release()

    def _after_push(self, result):
        if result == SyncResult.PUSHED:
            version = self.state.get("last_applied_version")
            self.toast.emit("success", f"Shared your progress as v{version} — "
                                       f"your friends are up to date.")
        elif result == SyncResult.NOTHING_TO_PUSH:
            self.toast.emit("warning", "No save files found for this world yet, so there was "
                                       "nothing to share.")
        elif result == SyncResult.STALE_CANCELLED:
            self.toast.emit("info", "Didn't share. Hit Play to pick up the newer save first.")

    def _safe_status(self):
        try:
            return sync.get_status(self.cfg, self.state)
        except Exception:
            log.exception("Status check failed")
            return ErrorSnapshot()
