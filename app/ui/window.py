"""The frameless application window: chrome, pages, overlays, tray glue."""

import logging
import threading

from PySide6.QtCore import QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect,
                               QGraphicsOpacityEffect, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..controller import Controller
from ..core import backups as backups_core
from ..core import config
from .about_page import AboutPage
from .backups_page import BackupsPage
from .invite_page import InvitePage
from .main_screen import MainPage
from .note_overlay import NoteOverlay
from .onboarding import OnboardingPage
from .overlay import ConfirmOverlay
from .settings import SettingsPage
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
        for p in (self.main_page, self.settings_page, self.onboarding_page,
                  self.invite_page, self.backups_page, self.about_page):
            self.pages.addWidget(p)

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

        # controller -> UI
        c.status_checking.connect(self.main_page.set_checking)
        c.status_changed.connect(self.main_page.set_status)
        c.phase_changed.connect(self.main_page.set_phase)
        c.toast.connect(self.toasts.show_toast)
        c.confirm_requested.connect(self._on_confirm_request)
        c.worlds_changed.connect(self._sync_world_header)
        c.friend_pushed.connect(self._on_friend_pushed)
        c.note_prompt.connect(self._on_note_prompt)
        self.note_overlay.submitted.connect(c.save_session_note)

        # onboarding / settings / sub-pages
        self.onboarding_page.finished.connect(self._finish_onboarding)
        self.onboarding_page.cancelled.connect(lambda: self._show_page(self.main_page))
        self.settings_page.saved.connect(self._save_settings)
        self.settings_page.cancelled.connect(lambda: self._show_page(self.main_page))
        self.settings_page.remove_world_requested.connect(self._remove_world)
        self.settings_page.about_requested.connect(
            lambda: self._show_page(self.about_page))
        self.invite_page.back_requested.connect(lambda: self._show_page(self.main_page))
        self.invite_page.share_link_saved.connect(
            lambda wid, link: c.update_world(wid, {"share_link": link or None}))
        self.backups_page.back_requested.connect(lambda: self._show_page(self.main_page))
        self.backups_page.restore_requested.connect(self._restore_backup)
        self.about_page.back_requested.connect(lambda: self._show_page(self.settings_page))

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

    def _open_backups(self):
        world = self.controller.active_world()
        if not world:
            return
        infos = backups_core.list_backups(config.backup_root_for(world["id"]))
        self.backups_page.load(world["world_name"], infos)
        self._show_page(self.backups_page)

    def _restore_backup(self, info):
        world = self.controller.active_world()
        if not world:
            return
        if not self.confirm.ask(
                "Restore this backup?",
                "Your current local save will be replaced (after being backed up "
                "itself, so nothing is lost). To put the whole group on the "
                "restored version, use “Save my progress now” afterwards.",
                danger_label="Restore", safe_label="Cancel"):
            return
        cfg = self.controller.cfg

        def worker():
            try:
                count = backups_core.restore_backup(
                    info.path, cfg["local_save_dir"], world["world_name"],
                    config.backup_root_for(world["id"]))
                if count:
                    self.controller.toast.emit(
                        "success", "Backup restored to this PC. Share it with "
                                   "“Save my progress now” if the group should use it.")
                else:
                    self.controller.toast.emit("warning", "That backup was empty — nothing changed.")
            except Exception:
                log.exception("Restore failed")
                self.controller.toast.emit("error", "The restore didn't complete — "
                                                    "your current save is untouched.")

        threading.Thread(target=worker, daemon=True, name="restore").start()
        self._show_page(self.main_page)

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
