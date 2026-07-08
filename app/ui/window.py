"""The frameless application window: chrome, pages, toasts, confirm overlay."""

from PySide6.QtCore import QPropertyAnimation, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect,
                               QGraphicsOpacityEffect, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..controller import Controller
from .main_screen import MainPage
from .onboarding import OnboardingPage
from .overlay import ConfirmOverlay
from .settings import SettingsPage
from .titlebar import TitleBar
from .toast import ToastHost

WINDOW_W, WINDOW_H = 512, 784
SHADOW_MARGIN = 16


class MainWindow(QWidget):
    def __init__(self, controller: Controller, parent=None):
        super().__init__(parent)
        self.controller = controller
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
        for p in (self.main_page, self.settings_page, self.onboarding_page):
            self.pages.addWidget(p)

        self.toasts = ToastHost(self.chrome)
        self.confirm = ConfirmOverlay(self.chrome)

        self._wire()

        if controller.has_config:
            self.main_page.set_player_name(controller.cfg.get("player_name", ""))
            self._show_page(self.main_page)
            controller.refresh_status()
        else:
            self.titlebar.settings_btn.hide()
            self._show_page(self.onboarding_page)

    # -- wiring ------------------------------------------------------------------
    def _wire(self):
        c = self.controller
        self.titlebar.settings_clicked.connect(self._open_settings)

        self.main_page.play_clicked.connect(c.start_play)
        self.main_page.save_clicked.connect(c.push_now)
        self.main_page.refresh_clicked.connect(lambda: c.refresh_status())

        c.status_checking.connect(self.main_page.set_checking)
        c.status_changed.connect(self.main_page.set_status)
        c.phase_changed.connect(self.main_page.set_phase)
        c.toast.connect(self.toasts.show_toast)
        c.confirm_requested.connect(self._on_confirm_request)

        self.onboarding_page.finished.connect(self._finish_onboarding)
        self.settings_page.saved.connect(self._save_settings)
        self.settings_page.cancelled.connect(lambda: self._show_page(self.main_page))

    def _on_confirm_request(self, request):
        answer = self.confirm.ask(request["title"], request["body"],
                                  danger_label=request.get("danger", "Overwrite"))
        request["answer"] = answer
        request["event"].set()

    def _finish_onboarding(self, cfg):
        self.controller.save_config(cfg)
        self.main_page.set_player_name(cfg.get("player_name", ""))
        self.titlebar.settings_btn.show()
        self._show_page(self.main_page)
        self.toasts.show_toast("success",
                               f"You're all set, {cfg.get('player_name', 'friend')}. "
                               f"Hit Play whenever you're ready.")

    def _open_settings(self):
        if self.pages.currentWidget() is self.onboarding_page:
            return
        self.settings_page.load(self.controller.cfg)
        self._show_page(self.settings_page)

    def _save_settings(self, cfg):
        self.controller.save_config(cfg)
        self.main_page.set_player_name(cfg.get("player_name", ""))
        self._show_page(self.main_page)
        self.toasts.show_toast("success", "Settings saved.")

    # -- page transitions ------------------------------------------------------------
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

    # -- lifecycle ----------------------------------------------------------------------
    def closeEvent(self, event):
        if self.controller.phase in ("waiting", "ingame", "pushing"):
            stay = not self.confirm.ask(
                "The game is still running",
                "If you close Dragonwilds Sync now, your progress won't be shared "
                "automatically when you finish playing.\n\n"
                "You can always share it later with “Save my progress now”.",
                danger_label="Close anyway",
                safe_label="Stay open",
            )
            if stay:
                event.ignore()
                return
        event.accept()
