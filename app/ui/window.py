"""The frameless application window: chrome, pages, overlays, tray glue."""

import logging
import threading

from PySide6.QtCore import QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect,
                               QGraphicsOpacityEffect, QMenu, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..controller import Controller
from ..core import backups as backups_core
from ..core import config, preflight
from .about_page import AboutPage
from .backups_page import BackupsPage
from .characters_page import CharactersPage
from .grimoire_page import GrimoirePage
from .invite_page import InvitePage
from .main_screen import MainPage
from .note_overlay import NoteOverlay
from .onboarding import OnboardingPage
from .overlay import ConfirmOverlay
from .preflight_page import PreflightPage
from .saga_page import SagaPage
from .settings import SettingsPage
from . import icons, theme
from .titlebar import TitleBar
from .toast import ToastHost
from .tray import TrayManager

log = logging.getLogger("dwsync.window")

WINDOW_W, WINDOW_H = 512, 784
SHADOW_MARGIN = 16


class MainWindow(QWidget):
    def __init__(self, controller: Controller, app_icon: QIcon, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._really_quit = False
        self._pending_update = None
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint
                            | Qt.WindowMinimizeButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(WINDOW_W, WINDOW_H)
        self.setWindowTitle("Dragonwilds Sync")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(*([SHADOW_MARGIN] * 4))
        self.chrome = QFrame()
        self.chrome.setObjectName("Chrome")
        outer.addWidget(self.chrome)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 170))
        shadow.setOffset(0, 8)
        self.chrome.setGraphicsEffect(shadow)

        chrome_box = QVBoxLayout(self.chrome)
        chrome_box.setContentsMargins(0, 4, 0, 0)
        chrome_box.setSpacing(0)

        self.titlebar = TitleBar()
        chrome_box.addWidget(self.titlebar)

        self.pages = QStackedWidget()
        chrome_box.addWidget(self.pages, 1)

        self.main_page = MainPage()
        self.settings_page = SettingsPage()
        self.onboarding_page = OnboardingPage()
        self.invite_page = InvitePage()
        self.backups_page = BackupsPage()
        self.about_page = AboutPage()
        self.preflight_page = PreflightPage()
        self.characters_page = CharactersPage()
        self.grimoire_page = GrimoirePage()
        self.saga_page = SagaPage()
        for p in (self.main_page, self.settings_page, self.onboarding_page,
                  self.invite_page, self.backups_page, self.about_page,
                  self.preflight_page, self.characters_page, self.grimoire_page,
                  self.saga_page):
            self.pages.addWidget(p)
        self._backup_ctx = None

        self.toasts = ToastHost(self.chrome)
        self.confirm = ConfirmOverlay(self.chrome)
        self.note_overlay = NoteOverlay(self.chrome)

        self.tray = TrayManager(app_icon, self)

        self._wire()

        if controller.has_config:
            self._sync_world_header()
            self._show_page(self.main_page)
            controller.refresh_status()
        else:
            self.titlebar.settings_btn.hide()
            self.onboarding_page.start_fresh()
            self._show_page(self.onboarding_page)

    # -- wiring -----------------------------------------------------------------
    def _wire(self):
        c = self.controller
        self.titlebar.settings_clicked.connect(self._open_settings)

        # main page
        self.main_page.play_clicked.connect(c.start_play)
        self.main_page.save_clicked.connect(c.push_now)
        self.main_page.refresh_clicked.connect(lambda: c.refresh_status())
        self.main_page.invite_clicked.connect(self._open_invite)
        self.main_page.world_selected.connect(c.set_active_world)
        self.main_page.add_world_clicked.connect(self._open_add_world)
        self.main_page.backups_clicked.connect(self._open_backups)
        self.main_page.next_claim_clicked.connect(c.toggle_next_claim)
        self.main_page.pass_turn_clicked.connect(self._pass_turn)
        self.main_page.update_clicked.connect(self._apply_update)
        self.main_page.characters_clicked.connect(self._open_characters)
        self.main_page.saga_clicked.connect(self._open_saga)
        self.saga_page.back_requested.connect(lambda: self._show_page(self.main_page))
        self.saga_page.export_requested.connect(c.export_saga)
        # (the grimoire deliberately has no menu entry — see _awaken_secret)

        # characters
        self.characters_page.back_requested.connect(lambda: self._show_page(self.main_page))
        self.characters_page.checkpoint_requested.connect(
            lambda stem, name: c.checkpoint_character(stem, name))
        self.characters_page.backups_requested.connect(self._open_char_backups)
        self.characters_page.travel_toggled.connect(c.set_character_travel)

        # the secret
        self.titlebar.secret_awakened.connect(self._awaken_secret)
        self.grimoire_page.back_requested.connect(
            lambda: self._show_page(self.characters_page))
        self.grimoire_page.bargain_requested.connect(self._strike_bargain)
        self.grimoire_page.ritual_started.connect(self._start_ritual)
        self.grimoire_page.ritual_finished.connect(self._finish_ritual)
        self.grimoire_page.label_saved.connect(c.save_skill_label)

        # controller -> UI
        c.status_checking.connect(self.main_page.set_checking)
        c.status_changed.connect(self.main_page.set_status)
        c.phase_changed.connect(self.main_page.set_phase)
        c.toast.connect(self.toasts.show_toast)
        c.confirm_requested.connect(self._on_confirm_request)
        c.worlds_changed.connect(self._sync_world_header)
        c.friend_pushed.connect(self._on_friend_pushed)
        c.note_prompt.connect(self._on_note_prompt)
        c.update_available.connect(self._on_update_available)
        c.nudge_received.connect(self._on_nudge_received)
        c.quit_for_update.connect(self._quit_for_update)
        c.run_on_ui.connect(lambda fn: fn())   # queued → runs on the GUI thread
        self.note_overlay.submitted.connect(c.save_session_note)

        # onboarding / settings / sub-pages
        self.onboarding_page.finished.connect(self._finish_onboarding)
        self.onboarding_page.cancelled.connect(lambda: self._show_page(self.main_page))
        self.settings_page.saved.connect(self._save_settings)
        self.settings_page.cancelled.connect(lambda: self._show_page(self.main_page))
        self.settings_page.remove_world_requested.connect(self._remove_world)
        self.settings_page.about_requested.connect(
            lambda: self._show_page(self.about_page))
        self.settings_page.preflight_requested.connect(self._open_preflight)
        self.settings_page.publish_update_requested.connect(self._publish_update)
        self.invite_page.back_requested.connect(lambda: self._show_page(self.main_page))
        self.invite_page.share_link_saved.connect(
            lambda wid, link: c.update_world(wid, {"share_link": link or None}))
        self.backups_page.back_requested.connect(self._backups_back)
        self.backups_page.restore_requested.connect(self._restore_backup)
        self.backups_page.checkpoint_requested.connect(self._create_checkpoint)
        self.backups_page.delete_requested.connect(self._delete_checkpoint)
        self.about_page.back_requested.connect(lambda: self._show_page(self.settings_page))
        self.preflight_page.back_requested.connect(lambda: self._show_page(self.settings_page))
        self.preflight_page.run_requested.connect(self._run_preflight)

        # tray
        self.tray.open_requested.connect(self._show_from_tray)
        self.tray.quit_requested.connect(self._quit_from_tray)

    # -- controller-driven bits ----------------------------------------------------
    def _sync_world_header(self):
        cfg = self.controller.cfg or {}
        self.main_page.set_player_name(cfg.get("player_name", ""))
        self.main_page.set_worlds(config.worlds(cfg), cfg.get("active_world"))

    def _on_confirm_request(self, request):
        answer = self.confirm.ask(request["title"], request["body"],
                                  danger_label=request.get("danger", "Overwrite"))
        request["answer"] = answer
        request["event"].set()

    def _on_friend_pushed(self, world_name, editor, version):
        if self.isVisible() and not self.isMinimized():
            self.toasts.show_toast(
                "info", f"{editor} shared v{version} of {world_name} — your turn?")
        else:
            self.tray.notify_friend_push(world_name, editor, version)

    def _on_note_prompt(self, world_id, version):
        if self.isVisible() and not self.isMinimized():
            self.note_overlay.open(world_id, version)

    # -- auto update -------------------------------------------------------------------
    def _on_update_available(self, info, world_name):
        self._pending_update = info
        self.main_page.show_update_bar(info.version, info.published_by)
        if not (self.isVisible() and not self.isMinimized()):
            self.tray.notify_update(info.version)

    def _apply_update(self):
        info = self._pending_update
        if not info:
            return
        if self.confirm.ask(
                f"Update to v{info.version}?",
                f"{info.published_by} published a new version"
                + (f":\n\n“{info.notes}”" if info.notes else ".")
                + "\n\nThe app will close, update itself, and reopen. Your worlds "
                  "and settings are kept.",
                danger_label="Update & restart", safe_label="Not now"):
            self.main_page.hide_update_bar()
            self.controller.apply_update(info)

    def _quit_for_update(self):
        self._really_quit = True
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()

    def _on_nudge_received(self, from_player, world_name):
        if self.isVisible() and not self.isMinimized():
            self.toasts.show_toast("info", f"{from_player} says it's your turn in {world_name}.")
        else:
            self.tray.notify_nudge(from_player, world_name)

    # -- turn nudge ----------------------------------------------------------------------
    def _pass_turn(self):
        players = self.controller.known_players()
        if not players:
            self.toasts.show_toast("info", "No friends have played this world yet — "
                                           "once they do, you can pass them the turn.")
            return
        menu = QMenu(self)
        header = menu.addAction("Tell a friend it's their turn")
        header.setEnabled(False)
        menu.addSeparator()
        for name in players:
            act = menu.addAction(icons.icon("send", theme.TEXT_DIM, 14), name)
            act.triggered.connect(lambda _=False, n=name: self.controller.send_turn_nudge(n))
        menu.exec(self.main_page.pass_btn.mapToGlobal(
            self.main_page.pass_btn.rect().bottomLeft()))

    # -- preflight -----------------------------------------------------------------------
    def _open_preflight(self):
        self._show_page(self.preflight_page)
        self._run_preflight()

    def _run_preflight(self):
        world = self.controller.active_world()
        if not world:
            return
        self.preflight_page.set_running()
        cfg = self.controller.cfg

        def worker():
            try:
                checks = preflight.run(cfg, world)
            except Exception:
                log.exception("Preflight failed")
                checks = []
            # widgets are rebuilt on the GUI thread, never from this worker
            self.controller.run_on_ui.emit(
                lambda: self.preflight_page.show_results(checks))

        threading.Thread(target=worker, daemon=True, name="preflight").start()

    def _publish_update(self):
        if self.confirm.ask(
                "Publish this version to friends?",
                f"This copies the running app (v{self.controller.app_version}) into "
                f"the shared folder so everyone in this world is offered the update. "
                f"Only do this after testing the new build yourself.",
                danger_label="Publish", safe_label="Cancel"):
            self.controller.publish_update()

    def _create_checkpoint(self, name):
        ctx = self._backup_ctx or {}
        if ctx.get("kind") == "character":
            self.controller.checkpoint_character(ctx["match"], name,
                                                 done=self._reload_backups)
        else:
            self.controller.create_checkpoint(name, done=self._reload_backups)

    def _delete_checkpoint(self, info):
        if self.confirm.ask(
                f"Delete “{info.name}”?",
                "This removes the checkpoint from this PC. Your current save and "
                "other backups are untouched.",
                danger_label="Delete", safe_label="Keep it"):
            backups_core.delete_backup(info.path)
            self._reload_backups()

    def _reload_backups(self):
        ctx = self._backup_ctx
        if not ctx:
            return
        root = ctx["root"]
        group = []
        if ctx["kind"] == "world":
            for av in self.controller.group_history():
                group.append(backups_core.BackupInfo(
                    path=av.path, stamp=av.modified, label=f"group_v{av.version}",
                    file_count=av.file_count))
        self.backups_page.load(ctx["title"],
                               backups_core.list_checkpoints(root),
                               backups_core.list_backups(root),
                               group_history=group)

    # -- onboarding & worlds -----------------------------------------------------------
    def _finish_onboarding(self, payload):
        c = self.controller
        world = config.make_world(payload["world_name"], payload["sync_dir"],
                                  share_link=payload.get("share_link"))
        if c.has_config:
            c.add_world(world)
        else:
            c.setup_first_config(payload["player_name"], payload["local_save_dir"], world)
        self.titlebar.settings_btn.show()
        self._sync_world_header()
        self._show_page(self.main_page)
        if payload["kind"] == "join":
            self.toasts.show_toast("success",
                                   f"Welcome to {payload['world_name']}. Hit Play — "
                                   f"the latest save comes to you.")
        else:
            self.toasts.show_toast("success",
                                   f"{payload['world_name']} is ready. Invite your "
                                   f"friends from the button up top.")

    def _open_add_world(self):
        self.onboarding_page.start_add_world(self.controller.player_name)
        self._show_page(self.onboarding_page)

    def _remove_world(self, world_id):
        world = config.world_by_id(self.controller.cfg, world_id)
        name = world["world_name"] if world else "this world"
        if self.confirm.ask(
                f"Forget {name}?",
                "This only removes it from the app on this PC. The shared folder, "
                "the saves, and your friends' setups are untouched — you can "
                "rejoin with an invite code any time.",
                danger_label="Forget world", safe_label="Keep it"):
            self.controller.remove_world(world_id)
            self._sync_world_header()
            self._show_page(self.main_page)
            if not self.controller.has_config:
                self.titlebar.settings_btn.hide()
                self.onboarding_page.start_fresh()
                self._show_page(self.onboarding_page)

    # -- settings ------------------------------------------------------------------------
    def _open_settings(self):
        if self.pages.currentWidget() is self.onboarding_page \
                and not self.controller.has_config:
            return
        self.settings_page.load(self.controller.cfg, self.controller.active_world())
        self._show_page(self.settings_page)

    def _save_settings(self, global_fields, world_fields):
        c = self.controller
        c.update_globals(global_fields)
        if world_fields:
            wid = world_fields.pop("id")
            c.update_world(wid, world_fields)
        self._sync_world_header()
        self._show_page(self.main_page)
        self.toasts.show_toast("success", "Settings saved.")
        c.refresh_status()

    # -- invite & backups ----------------------------------------------------------------
    def _open_invite(self):
        world = self.controller.active_world()
        if world:
            self.invite_page.load(world)
            self._show_page(self.invite_page)

    def _open_characters(self):
        self.characters_page.load(self.controller.list_characters(),
                                  set((self.controller.cfg or {}).get(
                                      "travel_characters") or []))
        self._show_page(self.characters_page)

    def _open_saga(self):
        world, manifest, stats, all_time = self.controller.saga_data()
        self.saga_page.load(world, manifest, stats, all_time,
                            me=self.controller.player_name)
        self._show_page(self.saga_page)

    # -- the secret --------------------------------------------------------------------
    def _awaken_secret(self):
        """The eye is the only door. No menu entry, no trace — five quick
        clicks on the titlebar mark, every time."""
        if not self.controller.has_config:
            return
        self._open_grimoire()

    def _open_grimoire(self):
        self.grimoire_page.load(self.controller.list_characters(),
                                self.controller.skill_labels(),
                                self.controller.pending_ritual())
        self._show_page(self.grimoire_page)

    def _strike_bargain(self, char_path, plan):
        wants = []
        if plan.skill_xp:
            wants.append(f"rewrite {len(plan.skill_xp)} skill"
                         f"{'s' if len(plan.skill_xp) != 1 else ''}")
        if plan.heal_vitals:
            wants.append("restore vitals")
        if plan.repair_all:
            wants.append("repair everything")
        if not self.confirm.ask(
                "Seal the bargain?",
                "The dragon will " + ", ".join(wants) + ".\n\n"
                "A checkpoint of the current character is taken first. This is "
                "experimental — if the game refuses the changed file, restore "
                "the checkpoint from Characters → Backups.",
                danger_label="Seal it", safe_label="Not yet"):
            return
        self.controller.apply_bargain(char_path, plan, done=self._open_grimoire)

    def _start_ritual(self, char_path):
        self.controller.start_ritual(char_path)
        self.toasts.show_toast(
            "info", "The ritual has begun. Go train exactly one skill for a "
                    "minute, quit to the menu, then return and finish it.")
        self._open_grimoire()

    def _finish_ritual(self):
        _char, gains = self.controller.finish_ritual()
        if not gains:
            self.toasts.show_toast("info", "The ritual saw nothing change — "
                                           "train a skill in game first.")
        else:
            self.grimoire_page.offer_ritual_labels(gains)
        self._open_grimoire()

    def _open_backups(self):
        world = self.controller.active_world()
        if not world:
            return
        self._backup_ctx = {
            "kind": "world",
            "title": world["world_name"],
            "save_dir": self.controller.cfg["local_save_dir"],
            "match": world["world_name"],
            "root": config.backup_root_for(world["id"]),
            "back_page": self.main_page,
        }
        self._reload_backups()
        self._show_page(self.backups_page)

    def _open_char_backups(self, stem):
        self._backup_ctx = {
            "kind": "character",
            "title": stem,
            "save_dir": str(self.controller.characters_dir()),
            "match": stem,
            "root": self.controller._char_backup_root(stem),
            "back_page": self.characters_page,
        }
        self._reload_backups()
        self._show_page(self.backups_page)

    def _backups_back(self):
        target = (self._backup_ctx or {}).get("back_page", self.main_page)
        self._show_page(target)

    def _restore_backup(self, info):
        ctx = self._backup_ctx
        if not ctx:
            return
        if ctx["kind"] == "world":
            body = ("Your current local save will be replaced (after being backed "
                    "up itself, so nothing is lost). To put the whole group on the "
                    "restored version, use “Save my progress now” afterwards.")
        else:
            body = (f"{ctx['title']}'s current file will be replaced (after being "
                    f"backed up itself, so nothing is lost). Make sure the game "
                    f"is closed first.")
        if not self.confirm.ask("Restore this backup?", body,
                                danger_label="Restore", safe_label="Cancel"):
            return

        def worker():
            try:
                count = backups_core.restore_backup(
                    info.path, ctx["save_dir"], ctx["match"], ctx["root"])
                if count:
                    self.controller.toast.emit(
                        "success", "Backup restored to this PC."
                        + (" Share it with “Save my progress now” if the group "
                           "should use it." if ctx["kind"] == "world" else ""))
                else:
                    self.controller.toast.emit("warning", "That backup was empty — nothing changed.")
            except Exception:
                log.exception("Restore failed")
                self.controller.toast.emit("error", "The restore didn't complete — "
                                                    "nothing was changed.")

        threading.Thread(target=worker, daemon=True, name="restore").start()
        self._backups_back()

    # -- page transitions ---------------------------------------------------------------------
    def _show_page(self, page):
        self.pages.setCurrentWidget(page)
        if not self.isVisible():
            return
        fx = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(fx)
        anim = QPropertyAnimation(fx, b"opacity", page)
        anim.setDuration(170)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.finished.connect(lambda: page.setGraphicsEffect(None))
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    # -- tray & lifecycle --------------------------------------------------------------------------
    def _show_from_tray(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self):
        self._really_quit = True
        self._show_from_tray()
        self.close()

    def _accept_quit(self, event):
        from PySide6.QtWidgets import QApplication
        event.accept()
        QApplication.instance().quit()

    def closeEvent(self, event):
        to_tray = (self.tray.available and not self._really_quit
                   and (self.controller.cfg or {}).get("close_to_tray", True)
                   and self.controller.has_config)
        if to_tray:
            event.ignore()
            self.hide()
            self.tray.show_minimized_tip()
            return

        # Actually quitting mid-session means losing the auto-share — confirm.
        if self.controller.phase in ("waiting", "ingame", "pushing"):
            stay = not self.confirm.ask(
                "The game is still running",
                "If you quit Dragonwilds Sync now, your progress won't be shared "
                "automatically when you finish playing.\n\n"
                "You can always share it later with “Save my progress now”.",
                danger_label="Quit anyway", safe_label="Stay open")
            if stay:
                self._really_quit = False
                event.ignore()
                return
        self._accept_quit(event)
