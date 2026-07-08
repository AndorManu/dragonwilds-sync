"""Characters: every hero on this PC — portraits, playtime, vault, travel."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QScrollArea, QVBoxLayout,
                               QWidget)

from ..core.characters import portrait_descriptor
from . import format as fmt
from . import icons, theme, widgets


class CharactersPage(QWidget):
    back_requested = Signal()
    checkpoint_requested = Signal(str, str)     # stem, name
    backups_requested = Signal(str)             # stem
    travel_toggled = Signal(str, bool)          # stem, travels

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 4, 28, 20)
        root.setSpacing(0)

        header = QHBoxLayout()
        back = widgets.icon_button("chevron-left", theme.TEXT_DIM, tooltip="Back")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        title = QLabel("Characters")
        title.setStyleSheet("font-size: 18px; font-weight: 650;")
        header.addSpacing(6)
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)
        root.addSpacing(6)

        intro = QLabel("Everyone who calls this PC home. Their progress lives in "
                       "their own file — the app keeps safety copies after every "
                       "session, and can carry a character between your PCs.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12.5px;")
        root.addWidget(intro)
        root.addSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body.setStyleSheet("background: transparent;")
        self.box = QVBoxLayout(self.body)
        self.box.setContentsMargins(0, 0, 6, 0)
        self.box.setSpacing(12)
        scroll.setWidget(self.body)
        root.addWidget(scroll, 1)
        root.addSpacing(8)

        hint = QLabel("Travel keeps a copy in the shared folder so the same "
                      "character follows you between your own PCs. It never "
                      "touches your friends' characters.")
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        root.addWidget(hint)

    def load(self, infos, travel_stems):
        while self.box.count():
            item = self.box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not infos:
            empty = QLabel("No characters found yet — create one in the game and "
                           "they'll show up here.")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 12.5px;"
                                f"padding: 30px;")
            self.box.addWidget(empty)
            self.box.addStretch(1)
            return

        for info in infos:
            self.box.addWidget(self._card(info, info.path.stem in travel_stems))
        self.box.addStretch(1)

    def _card(self, info, travels: bool):
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(widgets.Avatar(info.name, 46,
                                     portrait=portrait_descriptor(info)),
                      0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel(info.name)
        name.setStyleSheet(f"font-family: '{theme.display_family()}';"
                           f"font-size: 16px; font-weight: 650; border: none;")
        col.addWidget(name)
        hours = info.playtime_s / 3600
        meta_bits = [f"{hours:.1f} h in the wilds", f"{info.total_xp:,} total xp"]
        if info.last_played:
            meta_bits.append("last played " +
                             fmt.humanize(info.last_played.isoformat()))
        meta = QLabel("  ·  ".join(meta_bits))
        meta.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px; border: none;")
        meta.setWordWrap(True)
        col.addWidget(meta)
        vit_bits = []
        if info.health is not None:
            vit_bits.append(f"{info.health:.0f} hp")
        if info.inventory_slots:
            vit_bits.append(f"{info.inventory_slots} items carried")
        if vit_bits:
            vit = QLabel("  ·  ".join(vit_bits))
            vit.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 11.5px; border: none;")
            col.addWidget(vit)
        top.addLayout(col, 1)
        lay.addLayout(top)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        travel = QCheckBox("Travels with you")
        travel.setChecked(travels)
        travel.toggled.connect(
            lambda on, s=info.path.stem: self.travel_toggled.emit(s, on))
        actions.addWidget(travel)
        actions.addStretch(1)
        cp = widgets.make_button("Checkpoint", "subtle", "flag", height=28)
        cp.clicked.connect(lambda _=False, s=info.path.stem: self._checkpoint(s))
        actions.addWidget(cp)
        bk = widgets.make_button("Backups", "subtle", "archive", height=28)
        bk.clicked.connect(
            lambda _=False, s=info.path.stem: self.backups_requested.emit(s))
        actions.addWidget(bk)
        lay.addLayout(actions)
        return card

    def _checkpoint(self, stem):
        name, ok = QInputDialog.getText(
            self, "Character checkpoint", f"Name this snapshot of {stem}:",
            QLineEdit.Normal, "Before the bargain")
        if ok and name.strip():
            self.checkpoint_requested.emit(stem, name.strip())
