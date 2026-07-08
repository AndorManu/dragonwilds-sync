"""Bridges the sync core and the UI: worker threads in, Qt signals out.

v1.1: multi-world. The controller owns the v2 config; every call into the
sync core goes through ``config.effective_cfg`` + ``config.world_state`` so
the validated core keeps its original flat interface.
"""

import logging
import threading
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QTimer, Signal

from . import __version__
from .core import config, game, presence, storage, sync, webhook
from .core.sync import MANIFEST_SCHEMA, SyncResult

log = logging.getLogger("dwsync.controller")

STATUS_POLL_MS = 20_000


class ErrorSnapshot:
    kind = "error"
    history = None
    manifest_schema = None


@dataclass
class WorldStatus:
    """Everything the main screen needs about the active world."""
    world_id: str
    world_name: str
    snapshot: object                      # StatusSnapshot | ErrorSnapshot
    playing: dict | None = None           # someone's live presence (not me)
    next_claim: dict | None = None        # current "I've got next" holder
    newer_app_needed: bool = False


class Controller(QObject):
    status_checking = Signal()
    status_changed = Signal(object)          # WorldStatus
    phase_changed = Signal(str)              # idle/checking/launching/waiting/ingame/pushing
    toast = Signal(str, str)                 # kind, message
    confirm_requested = Signal(object)       # {"title","body","danger","event","answer"}
    worlds_changed = Signal()                # world list or active world changed
    friend_pushed = Signal(str, str, int)    # world_name, editor, version (for tray)
    note_prompt = Signal(str, int)           # world_id, version — offer a session note

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg, self.state = config.load()
        self.phase = "idle"
        self._busy = threading.Lock()
        self._seen_versions: dict[str, int] = {}

        self._poll = QTimer(self)
        self._poll.setInterval(STATUS_POLL_MS)
        self._poll.timeout.connect(self._poll_tick)
        if self.cfg:
            self._prime_seen_versions()
            self._poll.start()

    # -- config & worlds --------------------------------------------------------
    @property
    def has_config(self) -> bool:
        return bool(self.cfg and config.worlds(self.cfg))

    @property
    def player_name(self) -> str:
        return (self.cfg or {}).get("player_name", "")

    def active_world(self) -> dict | None:
        return config.active_world(self.cfg) if self.cfg else None

    def _flat_cfg(self, world=None) -> dict:
        world = world or self.active_world()
        return config.effective_cfg(self.cfg, world)

    def _wstate(self, world=None) -> dict:
        world = world or self.active_world()
        return config.world_state(self.state, world["id"])

    def _backup_root(self, world=None):
        world = world or self.active_world()
        return config.backup_root_for(world["id"])

    def _save_all(self):
        storage.save_config(self.cfg)
        storage.save_state(self.state)

    def setup_first_config(self, player_name: str, local_save_dir: str, world: dict):
        """Called once from onboarding (create or join path)."""
        self.cfg = self.cfg or {}
        base, _ = config.migrate_config(self.cfg if config.worlds(self.cfg) else {})
        base.update({"player_name": player_name, "local_save_dir": local_save_dir})
        base["worlds"] = config.worlds(base) + [world]
        base["active_world"] = world["id"]
        self.cfg = base
        self._save_all()
        self._prime_seen_versions()
        self._poll.start()
        self.worlds_changed.emit()
        self.refresh_status()

    def add_world(self, world: dict, activate=True):
        self.cfg["worlds"] = config.worlds(self.cfg) + [world]
        if activate:
            self.cfg["active_world"] = world["id"]
        self._save_all()
        self.worlds_changed.emit()
        self.refresh_status()

    def remove_world(self, world_id: str):
        """Forgets the world locally; shared folder and saves stay untouched."""
        self.cfg["worlds"] = [w for w in config.worlds(self.cfg) if w["id"] != world_id]
        self.state.get("worlds", {}).pop(world_id, None)
        if self.cfg.get("active_world") == world_id:
            remaining = config.worlds(self.cfg)
            self.cfg["active_world"] = remaining[0]["id"] if remaining else None
        self._save_all()
        self.worlds_changed.emit()
        self.refresh_status()

    def set_active_world(self, world_id: str):
        if self.cfg.get("active_world") == world_id:
            return
        self.cfg["active_world"] = world_id
        self._save_all()
        self.worlds_changed.emit()
        self.refresh_status()

    def update_world(self, world_id: str, fields: dict):
        world = config.world_by_id(self.cfg, world_id)
        if world:
            world.update(fields)
            self._save_all()
            self.worlds_changed.emit()

    def update_globals(self, fields: dict):
        self.cfg.update(fields)
        self._save_all()
        self.worlds_changed.emit()
        self.refresh_status()

    # -- status -------------------------------------------------------------------
    def refresh_status(self, silent=False):
        if not self.has_config:
            return
        if not silent:
            self.status_checking.emit()
        world = self.active_world()

        def worker():
            self.status_changed.emit(self._world_status(world))

        threading.Thread(target=worker, daemon=True, name="status").start()

    def _world_status(self, world) -> WorldStatus:
        try:
            snapshot = sync.get_status(self._flat_cfg(world), self._wstate(world))
        except Exception:
            log.exception("Status check failed")
            snapshot = ErrorSnapshot()
        playing = None
        next_claim = None
        try:
            playing = presence.who_is_playing(world["sync_dir"])
            if playing and playing.get("player") == self.player_name:
                playing = None  # my own marker (other machine/crash) isn't a warning
            next_claim = presence.who_has_next(world["sync_dir"])
        except Exception:
            log.exception("Presence check failed")
        newer = bool(getattr(snapshot, "manifest_schema", None)
                     and snapshot.manifest_schema > MANIFEST_SCHEMA)
        return WorldStatus(world_id=world["id"], world_name=world["world_name"],
                           snapshot=snapshot, playing=playing,
                           next_claim=next_claim, newer_app_needed=newer)

    def _prime_seen_versions(self):
        for w in config.worlds(self.cfg or {}):
            try:
                manifest = sync.get_shared_manifest(w["sync_dir"])
                self._seen_versions[w["id"]] = manifest["version"] if manifest else 0
            except Exception:
                self._seen_versions[w["id"]] = 0

    def _poll_tick(self):
        if not self.has_config:
            return
        if self.phase == "idle":
            self.refresh_status(silent=True)
        threading.Thread(target=self._scan_all_worlds, daemon=True,
                         name="world-scan").start()

    def _scan_all_worlds(self):
        """Notify (tray/toast) when any configured world gets a new save."""
        for w in config.worlds(self.cfg):
            try:
                manifest = sync.get_shared_manifest(w["sync_dir"])
            except Exception:
                continue
            if not manifest:
                continue
            last = self._seen_versions.get(w["id"], 0)
            if manifest["version"] > last:
                self._seen_versions[w["id"]] = manifest["version"]
                editor = manifest.get("last_editor", "Someone")
                if last and editor != self.player_name:
                    self.friend_pushed.emit(w["world_name"], editor, manifest["version"])

    # -- helpers used by workers ----------------------------------------------------
    def _set_phase(self, phase):
        self.phase = phase
        self.phase_changed.emit(phase)

    def _confirm(self, title, body, danger="Overwrite") -> bool:
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
        world = self.active_world()
        flat = self._flat_cfg(world)
        wstate = self._wstate(world)
        sync_dir = world["sync_dir"]
        started_at = None
        try:
            # Presence: warn up front if a friend is mid-session right now.
            playing = presence.who_is_playing(sync_dir)
            if playing and playing.get("player") != self.player_name:
                minutes = int((playing.get("age_s") or 0) // 60)
                if minutes < 1:
                    since = "moments"
                elif minutes < 120:
                    since = f"{minutes} min"
                else:
                    since = f"{minutes // 60} h"
                if not self._confirm(
                        f"{playing['player']} is in this world right now",
                        f"They started about {since} ago. If you both play, one "
                        f"session will end up overwriting the other.\n\n"
                        f"Best wait for their save — or play at your own risk.",
                        danger="Play anyway"):
                    self.toast.emit("info", f"Wise. You'll get a heads-up when "
                                            f"{playing['player']}'s save lands.")
                    return

            self._set_phase("checking")
            result, wstate = sync.do_pull(flat, wstate, self._log, self._confirm,
                                          self._backup_root(world))
            storage.save_state(self.state)

            if result == SyncResult.PULLED:
                self.toast.emit("success", "Latest save pulled in — you're starting "
                                           "fresh off your friends' progress.")
            elif result == SyncResult.CONFLICT_CANCELLED:
                self.toast.emit("info", "Kept your local progress. It'll be shared "
                                        "when you finish this session.")
            elif result == SyncResult.MISSING_FILES:
                self.toast.emit("warning", "The newest save hasn't finished syncing to "
                                           "this PC — you're playing your current local copy.")

            presence.start_playing(sync_dir, self.player_name,
                                   self.cfg.get("player_emoji", ""))
            presence.clear_next(sync_dir, self.player_name)  # my turn is now
            started_at = time.monotonic()

            if game.find_game_process():
                self.toast.emit("info", "Dragonwilds is already running — I'll share "
                                        "your progress when you close it.")
            else:
                self._set_phase("launching")
                how = game.launch_game(flat)
                log.info("Game launched via %s", how)

            if not game.process_watch_available():
                self._set_phase("idle")
                self.toast.emit("warning", "I can't watch for the game closing on this "
                                           "PC. Hit “Save my progress now” when you're done.")
                return

            self._set_phase("waiting")
            proc = game.find_game_process() or game.wait_for_game_start()
            if proc is None:
                presence.stop_playing(sync_dir, self.player_name)
                self._set_phase("idle")
                self.toast.emit("warning", "Never saw the game start. If you are playing, "
                                           "use “Save my progress now” when you're done.")
                return

            self._set_phase("ingame")
            game.wait_for_game_exit(proc)

            self._set_phase("pushing")
            result, wstate = sync.do_push(flat, wstate, self._log, self._confirm,
                                          self._backup_root(world))
            storage.save_state(self.state)
            duration = int(time.monotonic() - started_at) if started_at else None
            self._after_push(world, result, duration)
        except Exception:
            log.exception("Play flow failed")
            self.toast.emit("error", "Something went wrong during the session. Your save "
                                     "is still on this PC — try “Save my progress now”.")
        finally:
            try:
                presence.stop_playing(sync_dir, self.player_name)
            except Exception:
                pass
            self._set_phase("idle")
            self.status_changed.emit(self._world_status(world))
            self._busy.release()

    # -- manual push ------------------------------------------------------------------
    def push_now(self):
        if not self._busy.acquire(blocking=False):
            return
        threading.Thread(target=self._push_flow, daemon=True, name="push").start()

    def _push_flow(self):
        world = self.active_world()
        try:
            self._set_phase("pushing")
            result, _ = sync.do_push(self._flat_cfg(world), self._wstate(world),
                                     self._log, self._confirm, self._backup_root(world))
            storage.save_state(self.state)
            self._after_push(world, result, None)
        except Exception:
            log.exception("Manual push failed")
            self.toast.emit("error", "Couldn't share your save. Check that your cloud "
                                     "folder is reachable, then try again.")
        finally:
            self._set_phase("idle")
            self.status_changed.emit(self._world_status(world))
            self._busy.release()

    def _after_push(self, world, result, duration_s):
        if result == SyncResult.PUSHED:
            version = self._wstate(world).get("last_applied_version")
            self._seen_versions[world["id"]] = version
            try:
                sync.amend_history_entry(
                    world["sync_dir"], version,
                    duration_s=duration_s,
                    emoji=self.cfg.get("player_emoji", ""),
                    color=self.cfg.get("player_color", ""),
                )
            except Exception:
                log.exception("Could not annotate history entry")
            self.toast.emit("success", f"Shared your progress as v{version} — "
                                       f"your friends are up to date.")
            if world.get("webhook_url"):
                webhook.send_async(
                    world["webhook_url"],
                    f"🐉 {self.player_name} shared v{version} of "
                    f"{world['world_name']} — the wilds await.",
                    on_error=lambda e: self.toast.emit(
                        "warning", "Save shared fine, but the webhook didn't go "
                                   "through — check the URL in Settings."))
            self.note_prompt.emit(world["id"], version)
        elif result == SyncResult.NOTHING_TO_PUSH:
            self.toast.emit("warning", "No save files found for this world yet, so "
                                       "there was nothing to share.")
        elif result == SyncResult.STALE_CANCELLED:
            self.toast.emit("info", "Didn't share. Hit Play to pick up the newer save first.")

    # -- session notes ---------------------------------------------------------------
    def save_session_note(self, world_id: str, version: int, note: str):
        world = config.world_by_id(self.cfg, world_id)
        if not world or not note.strip():
            return

        def worker():
            try:
                if sync.amend_history_entry(world["sync_dir"], version,
                                            note=note.strip()[:200]):
                    self.status_changed.emit(self._world_status(world))
            except Exception:
                log.exception("Could not save session note")

        threading.Thread(target=worker, daemon=True, name="note").start()

    # -- turn claims -------------------------------------------------------------------
    def toggle_next_claim(self):
        world = self.active_world()

        def worker():
            try:
                claim = presence.who_has_next(world["sync_dir"])
                if claim and claim.get("player") == self.player_name:
                    presence.clear_next(world["sync_dir"], self.player_name)
                    self.toast.emit("info", "Your claim on the next turn is released.")
                elif claim:
                    self.toast.emit("info", f"{claim['player']} already has next — "
                                            f"talk it out in the group chat.")
                else:
                    presence.claim_next(world["sync_dir"], self.player_name,
                                        self.cfg.get("player_emoji", ""))
                    self.toast.emit("success", "Next turn is yours — friends will "
                                               "see it before they hit Play.")
                self.status_changed.emit(self._world_status(world))
            except Exception:
                log.exception("Turn claim failed")

        threading.Thread(target=worker, daemon=True, name="next").start()

    @property
    def app_version(self) -> str:
        return __version__
