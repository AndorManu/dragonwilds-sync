"""Bridges the sync core and the UI: worker threads in, Qt signals out.

Multi-world, and the home of the v1.2 feature glue. Everything that could
affect save integrity — health gating, sync-state checks, richer conflict
detail — happens here, *around* the frozen sync core, never inside it.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

import re

from . import __version__
from .core import (backups, characters, chime, config, discordrp, game, health,
                   paths, presence, saga, statuspage, storage, sync, update,
                   webhook, worldhistory)
from .core.sync import MANIFEST_SCHEMA, SyncResult, world_files


def _safe_dirname(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f⁦-⁩]', "_", name).strip()
    return cleaned or "unnamed"

log = logging.getLogger("dwsync.controller")

STATUS_POLL_MS = 20_000


class ErrorSnapshot:
    kind = "error"
    history = None
    manifest_schema = None


@dataclass
class WorldStatus:
    world_id: str
    world_name: str
    snapshot: object
    playing: dict | None = None
    next_claim: dict | None = None
    newer_app_needed: bool = False


class Controller(QObject):
    status_checking = Signal()
    status_changed = Signal(object)
    phase_changed = Signal(str)
    toast = Signal(str, str)
    confirm_requested = Signal(object)
    worlds_changed = Signal()
    friend_pushed = Signal(str, str, int)
    note_prompt = Signal(str, int)
    update_available = Signal(object, str)     # UpdateInfo, world_name
    nudge_received = Signal(str, str)           # from_player, world_name
    quit_for_update = Signal()
    # Worker threads must never touch widgets. Emitting a callable through
    # this signal marshals it onto the GUI thread (queued connection).
    run_on_ui = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg, self.state = config.load()
        self.phase = "idle"
        self._busy = threading.Lock()
        self._seen_versions: dict[str, int] = {}
        self._update_offered = False
        self._rp = discordrp.RichPresence(
            (self.cfg or {}).get("discord_app_id", ""))

        self._poll = QTimer(self)
        self._poll.setInterval(STATUS_POLL_MS)
        self._poll.timeout.connect(self._poll_tick)
        if self.cfg:
            self._prime_seen_versions()
            self._poll.start()
            self.check_updates()

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
        return config.effective_cfg(self.cfg, world or self.active_world())

    def _wstate(self, world=None) -> dict:
        return config.world_state(self.state, (world or self.active_world())["id"])

    def _backup_root(self, world=None):
        return config.backup_root_for((world or self.active_world())["id"])

    def _save_all(self):
        storage.save_config(self.cfg)
        storage.save_state(self.state)

    def setup_first_config(self, player_name, local_save_dir, world):
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

    def add_world(self, world, activate=True):
        self.cfg["worlds"] = config.worlds(self.cfg) + [world]
        if activate:
            self.cfg["active_world"] = world["id"]
        self._save_all()
        self.worlds_changed.emit()
        self.refresh_status()
        self.check_updates()

    def remove_world(self, world_id):
        self.cfg["worlds"] = [w for w in config.worlds(self.cfg) if w["id"] != world_id]
        self.state.get("worlds", {}).pop(world_id, None)
        if self.cfg.get("active_world") == world_id:
            remaining = config.worlds(self.cfg)
            self.cfg["active_world"] = remaining[0]["id"] if remaining else None
        self._save_all()
        self.worlds_changed.emit()
        self.refresh_status()

    def set_active_world(self, world_id):
        if self.cfg.get("active_world") == world_id:
            return
        self.cfg["active_world"] = world_id
        self._save_all()
        self.worlds_changed.emit()
        self.refresh_status()

    def update_world(self, world_id, fields):
        world = config.world_by_id(self.cfg, world_id)
        if world:
            world.update(fields)
            self._save_all()
            self.worlds_changed.emit()

    def update_globals(self, fields):
        self.cfg.update(fields)
        self._save_all()
        self._rp = discordrp.RichPresence(self.cfg.get("discord_app_id", ""))
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
        playing = next_claim = None
        try:
            playing = presence.who_is_playing(world["sync_dir"])
            if playing and playing.get("player") == self.player_name:
                playing = None
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
        threading.Thread(target=self._scan_all_worlds, daemon=True, name="world-scan").start()

    def _scan_all_worlds(self):
        for w in config.worlds(self.cfg):
            try:
                manifest = sync.get_shared_manifest(w["sync_dir"])
            except Exception:
                continue
            # nudges addressed to me
            try:
                nudge = presence.read_nudge_for(w["sync_dir"], self.player_name)
                if nudge:
                    presence.clear_nudge(w["sync_dir"])
                    self.nudge_received.emit(nudge.get("player", "A friend"), w["world_name"])
            except Exception:
                pass
            if not manifest:
                continue
            last = self._seen_versions.get(w["id"], 0)
            if manifest["version"] > last:
                self._seen_versions[w["id"]] = manifest["version"]
                editor = manifest.get("last_editor", "Someone")
                if last and editor != self.player_name:
                    self.friend_pushed.emit(w["world_name"], editor, manifest["version"])
        self.check_updates()

    # -- auto update ---------------------------------------------------------------
    def check_updates(self):
        if self._update_offered:
            return

        def worker():
            for w in config.worlds(self.cfg or {}):
                try:
                    info = update.check(w["sync_dir"], __version__)
                except Exception:
                    continue
                if info:
                    self._update_offered = True
                    self.update_available.emit(info, w["world_name"])
                    return

        threading.Thread(target=worker, daemon=True, name="update-check").start()

    def apply_update(self, info):
        try:
            if update.apply_update(info, paths.APP_DIR / "update"):
                self.quit_for_update.emit()
            else:
                self.toast.emit("info", "Updates apply from the installed app — "
                                        "grab the new build from the shared folder’s "
                                        "_app folder for now.")
        except Exception:
            log.exception("apply_update failed")
            self.toast.emit("error", "Couldn't apply the update. You can copy the new "
                                     "exe from the shared folder’s _app folder manually.")

    def publish_update(self):
        world = self.active_world()
        if not world:
            return

        def worker():
            try:
                if not update.is_frozen():
                    self.toast.emit("info", "Publishing works from the installed app "
                                            "(the .exe), not when running from source.")
                    return
                update.publish(world["sync_dir"], __version__, update.current_exe(),
                               self.player_name, notes="")
                self.toast.emit("success", f"Published v{__version__} to {world['world_name']}. "
                                           f"Friends will be offered the update automatically.")
            except Exception:
                log.exception("publish_update failed")
                self.toast.emit("error", "Couldn't publish the update to the shared folder.")

        threading.Thread(target=worker, daemon=True, name="publish").start()

    # -- worker helpers ------------------------------------------------------------
    def _set_phase(self, phase):
        self.phase = phase
        self.phase_changed.emit(phase)

    def _confirm(self, title, body, danger="Overwrite") -> bool:
        if "Overwrite" in title or "saved while" in title:
            detail = self._conflict_details()
            if detail:
                body = body + "\n\n" + detail
        request = {"title": title, "body": body, "danger": danger,
                   "event": threading.Event(), "answer": False}
        self.confirm_requested.emit(request)
        request["event"].wait()
        return request["answer"]

    def _conflict_details(self) -> str:
        """Sizes + times of the two saves, so a conflict choice is informed."""
        try:
            world = self.active_world()
            wn = world["world_name"]
            local = world_files(Path(self.cfg["local_save_dir"]), wn)
            shared = world_files(Path(world["sync_dir"]), wn)

            def describe(files):
                prim = next((f for f in files if f.suffix.lower() == ".sav"), None)
                if not prim:
                    return None
                st = prim.stat()
                when = datetime.fromtimestamp(st.st_mtime).strftime("%d %b %H:%M")
                return f"{st.st_size // 1024} KB · saved {when}"

            li, si = describe(local), describe(shared)
            lines = []
            if li:
                lines.append(f"Your save:  {li}")
            if si:
                lines.append(f"Their save: {si}")
            return "\n".join(lines)
        except Exception:
            return ""

    def _log(self, message):
        log.info(message)

    def _write_status(self, world):
        if not (self.cfg or {}).get("publish_status_page", True):
            return
        try:
            manifest = sync.get_shared_manifest(world["sync_dir"])
            statuspage.write(world["sync_dir"], world["world_name"], manifest,
                             presence.who_is_playing(world["sync_dir"]),
                             presence.who_has_next(world["sync_dir"]))
        except Exception:
            log.exception("status page write failed")

    # -- characters ------------------------------------------------------------------
    def characters_dir(self) -> Path:
        return characters.characters_dir(self.cfg or {})

    def list_characters(self):
        try:
            return characters.list_characters(self.characters_dir())
        except Exception:
            log.exception("Character listing failed")
            return []

    def _recent_character(self):
        infos = self.list_characters()
        return infos[0] if infos else None

    def _char_backup_root(self, stem: str) -> Path:
        return paths.BACKUP_DIR / "characters" / _safe_dirname(stem)

    def _char_flat_cfg(self, stem: str, world) -> dict:
        """A v1-shaped cfg that points the frozen sync core at a character."""
        travel_dir = Path(world["sync_dir"]) / "characters" / _safe_dirname(self.player_name)
        return {
            "player_name": self.player_name,
            "local_save_dir": str(self.characters_dir()),
            "world_name": stem,
            "sync_dir": str(travel_dir),
            "exe_path": None,
            "steam_app_id": paths.STEAM_APP_ID,
        }

    def _travel_stems(self) -> list[str]:
        stems = (self.cfg or {}).get("travel_characters") or []
        # glob metacharacters would confuse the core's {name}* matching
        return [s for s in stems if not any(ch in s for ch in "[]*?")]

    def _travel_pull(self, world):
        for stem in self._travel_stems():
            try:
                flat = self._char_flat_cfg(stem, world)
                wstate = config.world_state(self.state, f"char_{stem}")
                result, _ = sync.do_pull(flat, wstate, self._log, self._confirm,
                                         self._char_backup_root(stem))
                if result == SyncResult.PULLED:
                    self.toast.emit("info", f"Your character “{stem}” caught up "
                                            f"from your other PC.")
            except Exception:
                log.exception("Character travel pull failed for %s", stem)
        storage.save_state(self.state)

    def _travel_push(self, world):
        for stem in self._travel_stems():
            try:
                flat = self._char_flat_cfg(stem, world)
                wstate = config.world_state(self.state, f"char_{stem}")
                sync.do_push(flat, wstate, self._log, self._confirm,
                             self._char_backup_root(stem))
            except Exception:
                log.exception("Character travel push failed for %s", stem)
        storage.save_state(self.state)

    def _char_mtimes(self) -> dict:
        return {p: p.stat().st_mtime for p in
                characters.character_files(self.characters_dir())}

    def _changed_characters(self, before: dict):
        changed = []
        for p, mtime in self._char_mtimes().items():
            if before.get(p) != mtime:
                info = characters.parse_character(p)
                if info:
                    changed.append(info)
        return changed

    def _vault_characters(self, infos):
        """Rolling safety copies of characters touched this session."""
        for info in infos:
            try:
                files = [p for p in characters.character_files(info.path.parent)
                         if p.name.startswith(info.path.stem)]
                files += [Path(str(info.path) + ".backup")]
                files = [f for f in files if f.exists()]
                sync._backup_files(files, "session", self._char_backup_root(info.path.stem))
            except Exception:
                log.exception("Character vault backup failed")

    def set_character_travel(self, stem: str, travels: bool):
        stems = set((self.cfg or {}).get("travel_characters") or [])
        if travels:
            if any(ch in stem for ch in "[]*?"):
                self.toast.emit("warning", "That character's name confuses the sync "
                                           "matcher — rename it in game to enable travel.")
                return
            stems.add(stem)
        else:
            stems.discard(stem)
        self.cfg["travel_characters"] = sorted(stems)
        self._save_all()

    def checkpoint_character(self, stem: str, name: str, done=None):
        def worker():
            info = None
            try:
                info = backups.create_checkpoint(self.characters_dir(), stem, name,
                                                 self._char_backup_root(stem))
            except Exception:
                log.exception("Character checkpoint failed")
            if info:
                self.toast.emit("success", f"Checkpoint “{info.name}” saved for {stem}.")
            else:
                self.toast.emit("warning", "Couldn't find that character's files.")
            if done:
                self.run_on_ui.emit(done)

        threading.Thread(target=worker, daemon=True, name="char-checkpoint").start()

    # -- the Dragon's Bargain ----------------------------------------------------------
    def apply_bargain(self, char_path, plan, done=None):
        def worker():
            try:
                if game.find_game_process():
                    self.toast.emit("warning", "Close the game first — bargains struck "
                                               "while it runs are lost when it saves.")
                    return
                changes = characters.apply_edits(char_path, plan,
                                                 self._char_backup_root(Path(char_path).stem))
                if changes:
                    self.toast.emit("success", "The bargain is sealed. A checkpoint of "
                                               "the old self was kept, just in case.")
                else:
                    self.toast.emit("info", "Nothing to change — the dragon shrugs.")
            except Exception:
                log.exception("Bargain failed")
                self.toast.emit("error", "The bargain failed — your character file "
                                         "was left untouched.")
            finally:
                if done:
                    self.run_on_ui.emit(done)

        threading.Thread(target=worker, daemon=True, name="bargain").start()

    # -- identify ritual ----------------------------------------------------------------
    def skill_labels(self) -> dict:
        return characters.load_skill_labels(paths.APP_DIR)

    def save_skill_label(self, skill_id: str, label: str):
        labels = self.skill_labels()
        labels[skill_id] = label
        characters.save_skill_labels(paths.APP_DIR, labels)

    def start_ritual(self, char_path):
        storage.write_json(paths.APP_DIR / "ritual.json", {
            "char": str(char_path),
            "skills": characters.snapshot_skills(char_path),
        })

    def pending_ritual(self) -> dict | None:
        return storage.read_json(paths.APP_DIR / "ritual.json")

    def finish_ritual(self):
        ritual = self.pending_ritual()
        if not ritual:
            return None, []
        after = characters.snapshot_skills(ritual["char"])
        gains = characters.diff_skills(ritual.get("skills") or {}, after)
        (paths.APP_DIR / "ritual.json").unlink(missing_ok=True)
        return ritual["char"], gains

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
        world_name = world["world_name"]
        started_at = None
        try:
            playing = presence.who_is_playing(sync_dir)
            if playing and playing.get("player") != self.player_name:
                minutes = int((playing.get("age_s") or 0) // 60)
                since = "moments" if minutes < 1 else (
                    f"{minutes} min" if minutes < 120 else f"{minutes // 60} h")
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
            if health.shared_still_syncing(sync_dir, world_name):
                self.toast.emit("warning", "The shared folder is still downloading the "
                                           "latest save — launching your current copy for now.")
            else:
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

            self._travel_pull(world)

            recent = self._recent_character()
            presence.start_playing(
                sync_dir, self.player_name, self.cfg.get("player_emoji", ""),
                character=recent.name if recent else "",
                portrait=characters.portrait_descriptor(recent) if recent else "")
            presence.clear_next(sync_dir, self.player_name)
            self._write_status(world)
            char_mtimes_before = self._char_mtimes()
            started_at = time.monotonic()

            if game.find_game_process():
                self.toast.emit("info", "Dragonwilds is already running — I'll share "
                                        "your progress when you close it.")
            else:
                self._set_phase("launching")
                if self.cfg.get("play_chime", True):
                    chime.play()
                log.info("Game launched via %s", game.launch_game(flat))

            if not game.process_watch_available():
                self._set_phase("idle")
                self.toast.emit("warning", "I can't watch for the game closing on this "
                                           "PC. Hit “Save my progress now” when you're done.")
                return

            self._set_phase("waiting")
            proc = game.find_game_process() or game.wait_for_game_start()
            if proc is None:
                presence.stop_playing(sync_dir, self.player_name)
                self._write_status(world)
                self._set_phase("idle")
                self.toast.emit("warning", "Never saw the game start. If you are playing, "
                                           "use “Save my progress now” when you're done.")
                return

            self._set_phase("ingame")
            try:
                self._rp.set_playing(world["world_name"],
                                     recent.name if recent else "")
            except Exception:
                log.debug("Rich presence failed", exc_info=True)
            game.wait_for_game_exit(proc)
            self._rp.clear()

            self._set_phase("pushing")
            duration = int(time.monotonic() - started_at) if started_at else None
            played = self._changed_characters(char_mtimes_before)
            self._vault_characters(played)
            self._travel_push(world)
            self._do_push_guarded(world, flat, wstate, duration,
                                  played[0] if played else self._recent_character())
        except Exception:
            log.exception("Play flow failed")
            self.toast.emit("error", "Something went wrong during the session. Your save "
                                     "is still on this PC — try “Save my progress now”.")
        finally:
            try:
                presence.stop_playing(sync_dir, self.player_name)
                self._write_status(world)
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
            self._do_push_guarded(world, self._flat_cfg(world), self._wstate(world), None)
        except Exception:
            log.exception("Manual push failed")
            self.toast.emit("error", "Couldn't share your save. Check that your cloud "
                                     "folder is reachable, then try again.")
        finally:
            self._set_phase("idle")
            self.status_changed.emit(self._world_status(world))
            self._busy.release()

    def _do_push_guarded(self, world, flat, wstate, duration_s, played_char=None):
        """Health-gate the push so a corrupt save can't poison the group."""
        save_dir = Path(flat["local_save_dir"])
        world_name = flat["world_name"]
        if world_files(save_dir, world_name):
            hp = health.check_local_save(save_dir, world_name)
            if not hp.ok:
                self.toast.emit("warning", f"Your save looks {hp.reason}, so I didn't share "
                                           f"it — that protects everyone from a bad file. "
                                           f"Your friends keep the last good save.")
                return
        result, wstate = sync.do_push(flat, wstate, self._log, self._confirm,
                                      self._backup_root(world))
        storage.save_state(self.state)
        self._after_push(world, result, duration_s, played_char)

    def _after_push(self, world, result, duration_s, played_char=None):
        if result == SyncResult.PUSHED:
            version = self._wstate(world).get("last_applied_version")
            self._seen_versions[world["id"]] = version
            played_char = played_char or self._recent_character()
            try:
                sync.amend_history_entry(
                    world["sync_dir"], version, duration_s=duration_s,
                    emoji=self.cfg.get("player_emoji", ""),
                    color=self.cfg.get("player_color", ""),
                    character=played_char.name if played_char else "",
                    portrait=characters.portrait_descriptor(played_char)
                    if played_char else "")
            except Exception:
                log.exception("Could not annotate history entry")
            try:
                worldhistory.archive_version(world["sync_dir"],
                                             world["world_name"], version)
                saga.bump_stats(world["sync_dir"], self.player_name, duration_s)
                saga.write_saga(world["sync_dir"], world["world_name"],
                                sync.get_shared_manifest(world["sync_dir"]))
            except Exception:
                log.exception("Post-push extras failed")
            self._write_status(world)
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
    def save_session_note(self, world_id, version, note):
        world = config.world_by_id(self.cfg, world_id)
        if not world or not note.strip():
            return

        def worker():
            try:
                if sync.amend_history_entry(world["sync_dir"], version, note=note.strip()[:200]):
                    self._write_status(world)
                    self.status_changed.emit(self._world_status(world))
            except Exception:
                log.exception("Could not save session note")

        threading.Thread(target=worker, daemon=True, name="note").start()

    # -- turn claims + nudges ----------------------------------------------------------
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
                self._write_status(world)
                self.status_changed.emit(self._world_status(world))
            except Exception:
                log.exception("Turn claim failed")

        threading.Thread(target=worker, daemon=True, name="next").start()

    def known_players(self) -> list[str]:
        """Other players seen in the active world's history — for the nudge picker."""
        world = self.active_world()
        names = []
        try:
            manifest = sync.get_shared_manifest(world["sync_dir"])
            for entry in (manifest or {}).get("history", []):
                who = entry.get("editor")
                if who and who != self.player_name and who not in names:
                    names.append(who)
        except Exception:
            pass
        return list(reversed(names))

    def send_turn_nudge(self, to_player):
        world = self.active_world()

        def worker():
            try:
                presence.send_nudge(world["sync_dir"], self.player_name, to_player,
                                    self.cfg.get("player_emoji", ""))
                self.toast.emit("success", f"Nudged {to_player} — they'll get a ping "
                                           f"that it's their turn.")
                if world.get("webhook_url"):
                    webhook.send_async(
                        world["webhook_url"],
                        f"🐉 {self.player_name} passed the turn to {to_player} "
                        f"in {world['world_name']}.")
            except Exception:
                log.exception("Nudge failed")

        threading.Thread(target=worker, daemon=True, name="nudge").start()

    # -- checkpoints -------------------------------------------------------------------
    def create_checkpoint(self, name, done=None):
        world = self.active_world()

        def worker():
            info = None
            try:
                info = backups.create_checkpoint(
                    self.cfg["local_save_dir"], world["world_name"], name,
                    self._backup_root(world))
            except Exception:
                log.exception("Checkpoint failed")
            if info:
                self.toast.emit("success", f"Checkpoint “{info.name}” saved. Restore it "
                                           f"any time from Backups.")
            else:
                self.toast.emit("warning", "No local save to checkpoint yet.")
            if done:
                self.run_on_ui.emit(done)

        threading.Thread(target=worker, daemon=True, name="checkpoint").start()

    # -- saga & group history -----------------------------------------------------------
    def saga_data(self):
        """(world, manifest, stats, all_time) for the saga page."""
        world = self.active_world()
        if not world:
            return None, None, {}, False
        try:
            manifest = sync.get_shared_manifest(world["sync_dir"])
            stats, all_time = saga.combined_stats(world["sync_dir"], manifest)
            return world, manifest, stats, all_time
        except Exception:
            log.exception("Saga read failed")
            return world, None, {}, False

    def export_saga(self):
        world = self.active_world()
        if not world:
            return

        def worker():
            try:
                manifest = sync.get_shared_manifest(world["sync_dir"])
                path = saga.write_saga(world["sync_dir"], world["world_name"], manifest)
                if path:
                    import os as _os
                    _os.startfile(str(path))  # noqa: S606
                    self.toast.emit("success", "The chronicle is written — it lives "
                                               "in the shared folder for everyone.")
                else:
                    self.toast.emit("warning", "Couldn't write the chronicle just now.")
            except Exception:
                log.exception("Saga export failed")
                self.toast.emit("error", "Couldn't write the chronicle just now.")

        threading.Thread(target=worker, daemon=True, name="saga").start()

    def group_history(self):
        world = self.active_world()
        if not world:
            return []
        try:
            return worldhistory.list_versions(world["sync_dir"])
        except Exception:
            log.exception("Group history listing failed")
            return []

    @property
    def app_version(self) -> str:
        return __version__
