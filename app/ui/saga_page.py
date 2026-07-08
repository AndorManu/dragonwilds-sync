"""The Saga: the fellowship's totals and the world's chronicle."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QScrollArea, QVBoxLayout, QWidget)

from . import format as fmt
from . import theme, widgets


class SagaPage(QWidget):
    back_requested = Signal()
    export_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 4, 28, 20)
        root.setSpacing(0)

        header = QHBoxLayout()
        back = widgets.icon_button("chevron-left", theme.TEXT_DIM, tooltip="Back")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        self.title = QLabel("The Saga")
        self.title.setStyleSheet(
            f"font-family: '{theme.display_family()}'; font-size: 19px;"
            f"font-weight: 650; color: {theme.GOLD_TEXT};")
        header.addSpacing(6)
        header.addWidget(self.title)
        header.addStretch(1)
        export = widgets.make_button("Chronicle", "ghost", "external", height=32)
        export.setToolTip("Writes a shareable saga.html into the shared folder "
                          "and opens it")
        export.clicked.connect(self.export_requested.emit)
        header.addWidget(export)
        root.addLayout(header)
        root.addSpacing(10)

        self.scope_label = QLabel("")
        self.scope_label.setProperty("role", "hint")
        root.addWidget(self.scope_label)
        root.addSpacing(8)

        fellowship = QLabel("THE FELLOWSHIP")
        fellowship.setObjectName("SectionLabel")
        root.addWidget(fellowship)
        root.addSpacing(6)

        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(10)
        root.addLayout(self.stats_grid)
        root.addSpacing(12)

        chronicle = QLabel("THE CHRONICLE")
        chronicle.setObjectName("SectionLabel")
        root.addWidget(chronicle)
        root.addSpacing(6)

        card = QFrame()
        card.setObjectName("Card")
        wrap = QVBoxLayout(card)
        wrap.setContentsMargins(6, 6, 6, 6)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body.setStyleSheet("background: transparent;")
        self.box = QVBoxLayout(self.body)
        self.box.setContentsMargins(12, 8, 12, 8)
        self.box.setSpacing(0)
        scroll.setWidget(self.body)
        wrap.addWidget(scroll)
        root.addWidget(card, 1)

    def load(self, world, manifest, stats, all_time, me=""):
        name = world["world_name"] if world else "—"
        self.title.setText(f"The Saga of {name}")
        history = (manifest or {}).get("history", [])
        scope = "all time" if all_time else f"the last {len(history)} sessions"
        self.scope_label.setText(f"Totals cover {scope}.")

        while self.stats_grid.count():
            item = self.stats_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        ranked = sorted(stats.items(), key=lambda kv: -kv[1].get("seconds", 0))
        for i, (player, s) in enumerate(ranked[:8]):
            self.stats_grid.addWidget(
                self._stat_card(player, s, me, crown=(i == 0 and len(ranked) > 1)),
                i // 2, i % 2)
        if not ranked:
            empty = QLabel("No sessions recorded yet.")
            empty.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 12px;")
            self.stats_grid.addWidget(empty, 0, 0)

        while self.box.count():
            item = self.box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        noted = [e for e in reversed(history) if e.get("note")]
        if not noted:
            empty = QLabel("No notes in the chronicle yet — they're written after "
                           "each session.")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 12px;"
                                f"padding: 22px;")
            self.box.addWidget(empty)
        for i, entry in enumerate(noted):
            self.box.addWidget(self._chronicle_row(entry, me, first=(i == 0)))
        self.box.addStretch(1)

    def _stat_card(self, player, s, me, crown=False):
        card = QFrame()
        card.setObjectName("Card")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)
        lay.addWidget(widgets.Avatar(player, 34))
        col = QVBoxLayout()
        col.setSpacing(1)
        title = ("You" if player == me else player) + ("  👑" if crown else "")
        name = QLabel(title)
        name.setStyleSheet("border: none; font-size: 13px; font-weight: 650;")
        hours = s.get("seconds", 0) / 3600
        meta = QLabel(f"{s.get('sessions', 0)} sessions · {hours:.1f} h")
        meta.setStyleSheet(f"border: none; color: {theme.TEXT_DIM}; font-size: 11.5px;")
        col.addWidget(name)
        col.addWidget(meta)
        lay.addLayout(col, 1)
        return card

    def _chronicle_row(self, entry, me, first=False):
        row = QWidget()
        if not first:
            row.setStyleSheet(f"border-top: 1px solid {theme.BORDER_SOFT};")
        lay = QVBoxLayout(row)
        lay.setContentsMargins(2, 9, 2, 9)
        lay.setSpacing(3)
        note = QLabel(f"“{entry.get('note', '')}”")
        note.setWordWrap(True)
        note.setStyleSheet(
            f"border: none; color: {theme.GOLD_TEXT}; font-size: 14px;"
            f"font-family: '{theme.voice_family()}'; font-style: italic;")
        lay.addWidget(note)
        editor = entry.get("editor", "?")
        who = "You" if editor == me else editor
        char = f" as {entry['character']}" if entry.get("character") else ""
        meta = QLabel(f"{who}{char} · v{entry.get('version', '?')} · "
                      f"{fmt.humanize(entry.get('timestamp', ''))}")
        meta.setStyleSheet(f"border: none; color: {theme.TEXT_FAINT}; font-size: 11px;")
        lay.addWidget(meta)
        return row
