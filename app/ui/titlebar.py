"""Custom titlebar for the frameless window: mark, wordmark, window controls.

The dragon-eye mark keeps a secret: five quick clicks wake it.
"""

from PySide6.QtCore import QElapsedTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from . import icons, theme, widgets

SECRET_CLICKS = 5
SECRET_WINDOW_MS = 3000


class SecretMark(QLabel):
    """The dragon eye. It notices being poked."""

    awakened = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPixmap(icons.pixmap("dragon", theme.ACCENT, 18))
        self._clicks = 0
        self._timer = QElapsedTimer()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if not self._timer.isValid() or self._timer.elapsed() > SECRET_WINDOW_MS:
                self._clicks = 0
                self._timer.restart()
            self._clicks += 1
            if self._clicks >= SECRET_CLICKS:
                self._clicks = 0
                self._timer.invalidate()
                self.awakened.emit()
        super().mousePressEvent(e)


class TitleBar(QFrame):
    settings_clicked = Signal()
    secret_awakened = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(46)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 10, 0)
        row.setSpacing(8)

        mark = SecretMark()
        mark.awakened.connect(self.secret_awakened.emit)
        row.addWidget(mark)

        title = QLabel("DRAGONWILDS SYNC")
        title.setObjectName("TitleText")
        row.addWidget(title)
        row.addStretch(1)

        self.settings_btn = widgets.icon_button(
            "gear", theme.TEXT_DIM, "titlebar", 16, "Settings")
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        row.addWidget(self.settings_btn)

        minimize = widgets.icon_button("minus", theme.TEXT_DIM, "titlebar", 16, "Minimize")
        minimize.clicked.connect(lambda: self.window().showMinimized())
        row.addWidget(minimize)

        close = widgets.icon_button("x", theme.TEXT_DIM, "titlebarClose", 16, "Close")
        close.clicked.connect(lambda: self.window().close())
        row.addWidget(close)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()
        super().mousePressEvent(e)
