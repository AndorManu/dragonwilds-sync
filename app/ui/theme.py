"""Design system: palette, typography, and the global stylesheet.

A dark-fantasy game-launcher look: deep warm-obsidian base, cinematic depth,
an emerald "go" accent for action and an ember-gold accent for identity and
attention. Cinzel display type carries the fantasy; a clean sans keeps the
body legible. Red strictly for destruction.
"""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ..core import paths
from . import fonts

# -- palette ----------------------------------------------------------------
BG           = "#0A0D12"   # window base (deep warm obsidian)
BG_HI        = "#10161E"   # top of the ambient gradient
SURFACE      = "#12191F"   # cards
SURFACE_2    = "#1A232C"   # raised elements, hover fills
SURFACE_GLASS = "rgba(22, 30, 39, 0.72)"  # frosted panels over the banner
FIELD_BG     = "#0D131A"   # inputs sit slightly below the surface
BORDER       = "#222E39"
BORDER_SOFT  = "#19222C"
BORDER_GOLD  = "#3A3223"   # faint warm hairline for fantasy framing
TEXT         = "#ECEFF3"
TEXT_DIM     = "#9AA7B6"
TEXT_FAINT   = "#5E6B7A"
ACCENT       = "#3ECF8E"   # dragonfire emerald — the "go / play" colour
ACCENT_HOVER = "#55DCA0"
ACCENT_TEAL  = "#1FA89B"   # gradient partner
ON_ACCENT    = "#07130D"   # text on emerald
EMBER        = "#E8A23D"   # ember gold — identity, titles, flourishes
EMBER_HI     = "#F6C56A"
EMBER_DEEP   = "#B9761F"
GOLD_TEXT    = "#E6C892"   # legible gold for text over dark art
AMBER        = "#F2B441"
RED          = "#E5484D"
RED_HOVER    = "#EF5E63"

AVATAR_COLORS = ["#3ECF8E", "#5EA2EF", "#B78AF7", "#F2B441",
                 "#EF6E88", "#4FC7D4", "#9BCB57", "#F09B5C"]

FONT_STACK = '"Segoe UI Variable Display", "Segoe UI", sans-serif'


def display_family() -> str:
    return fonts.DISPLAY


def deco_family() -> str:
    return fonts.DISPLAY_DECO


def voice_family() -> str:
    return fonts.VOICE


UI_CACHE = paths.APP_DIR / "ui"

_CHEVRON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    f'stroke="{TEXT_DIM}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="6 9 12 15 18 9"/></svg>'
)

_CHECK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    f'stroke="{ON_ACCENT}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="20 6 9 17 4 12"/></svg>'
)


def _write_qss_assets() -> tuple[str, str]:
    """QSS image: url() needs real files; render the few we use to disk."""
    UI_CACHE.mkdir(parents=True, exist_ok=True)
    chevron = UI_CACHE / "chevron-down.svg"
    chevron.write_text(_CHEVRON_SVG, encoding="utf-8")
    check = UI_CACHE / "check.svg"
    check.write_text(_CHECK_SVG, encoding="utf-8")
    return chevron.as_posix(), check.as_posix()


def build_qss() -> str:
    chevron, check = _write_qss_assets()
    return f"""
* {{
    font-family: {FONT_STACK};
    outline: none;
}}
QWidget {{ color: {TEXT}; font-size: 13px; }}

#Chrome {{
    background: qlineargradient(x1:0, y1:0, x2:0.35, y2:1,
                stop:0 {BG_HI}, stop:0.55 {BG}, stop:1 #070A0E);
    border: 1px solid {BORDER};
    border-radius: 16px;
}}

/* -- titlebar ----------------------------------------------------------- */
#TitleBar {{ background: transparent; }}
#TitleText {{
    color: {GOLD_TEXT};
    font-family: "{fonts.DISPLAY}";
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 3px;
}}
QPushButton[variant="titlebar"], QPushButton[variant="titlebarClose"] {{
    background: transparent;
    border: none;
    border-radius: 7px;
    min-width: 34px;  max-width: 34px;
    min-height: 28px; max-height: 28px;
}}
QPushButton[variant="titlebar"]:hover  {{ background: {SURFACE_2}; }}
QPushButton[variant="titlebar"]:pressed {{ background: {BORDER}; }}
QPushButton[variant="titlebarClose"]:hover  {{ background: #C33A40; }}
QPushButton[variant="titlebarClose"]:pressed {{ background: #A63237; }}

/* -- cards -------------------------------------------------------------- */
#Card {{
    background: {SURFACE};
    border: 1px solid {BORDER_SOFT};
    border-radius: 14px;
}}
#GlassCard {{
    background: {SURFACE_GLASS};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
#HeroHeadline {{
    font-family: "{fonts.DISPLAY}";
    font-size: 22px; font-weight: 600; letter-spacing: 0.5px;
}}
#HeroSubline  {{ font-size: 12.5px; color: {TEXT_DIM}; }}
#SectionLabel {{
    font-family: "{fonts.DISPLAY}";
    font-size: 11px; font-weight: 600; letter-spacing: 2.5px;
    color: {EMBER};
}}
#FooterText   {{ font-size: 11px; color: {TEXT_FAINT}; }}
#WorldTitle {{
    font-family: "{fonts.DISPLAY_DECO}";
    font-size: 30px; font-weight: 700; color: #FFFFFF;
    letter-spacing: 1px;
}}
#HeroPill {{
    font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
}}

/* -- buttons ------------------------------------------------------------ */
QPushButton[variant="primary"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #33C286, stop:1 {ACCENT_TEAL});
    color: {ON_ACCENT};
    border: none;
    border-radius: 12px;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 0 24px;
}}
QPushButton[variant="primary"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #3FD494, stop:1 #23BCAD);
}}
QPushButton[variant="primary"]:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #29A872, stop:1 #17897E);
}}
QPushButton[variant="primary"]:disabled {{
    background: {SURFACE_2};
    color: {TEXT_FAINT};
}}

QPushButton[variant="ember"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {EMBER}, stop:1 {EMBER_DEEP});
    color: #1A1206;
    border: none;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 0 22px;
}}
QPushButton[variant="ember"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {EMBER_HI}, stop:1 {EMBER});
}}
QPushButton[variant="ember"]:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {EMBER_DEEP}, stop:1 #8F5A16);
}}
QPushButton[variant="ember"]:disabled {{
    background: {SURFACE_2};
    color: {TEXT_FAINT};
}}

QPushButton[variant="ghost"] {{
    background: transparent;
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 0 18px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton[variant="ghost"]:hover {{
    background: {SURFACE_2};
    color: {TEXT};
    border-color: {BORDER};
}}
QPushButton[variant="ghost"]:pressed {{ background: {BORDER_SOFT}; }}
QPushButton[variant="ghost"]:disabled {{ color: {TEXT_FAINT}; border-color: {BORDER_SOFT}; }}

QPushButton[variant="danger"] {{
    background: {RED};
    color: #FFF3F3;
    border: none;
    border-radius: 10px;
    padding: 0 18px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton[variant="danger"]:hover  {{ background: {RED_HOVER}; }}
QPushButton[variant="danger"]:pressed {{ background: #C93C41; }}

QPushButton[variant="subtle"] {{
    background: transparent;
    color: {TEXT_DIM};
    border: none;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton[variant="subtle"]:hover  {{ background: {SURFACE_2}; color: {TEXT}; }}
QPushButton[variant="subtle"]:pressed {{ background: {BORDER_SOFT}; }}

QPushButton[variant="chip"] {{
    background: {SURFACE_2};
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton[variant="chip"]:hover {{ color: {ACCENT}; border-color: {ACCENT}; }}

QPushButton[variant="icon"] {{
    background: transparent;
    border: none;
    border-radius: 8px;
    min-width: 30px;  max-width: 30px;
    min-height: 30px; max-height: 30px;
}}
QPushButton[variant="icon"]:hover  {{ background: {SURFACE_2}; }}
QPushButton[variant="icon"]:pressed {{ background: {BORDER_SOFT}; }}

/* -- inputs --------------------------------------------------------------*/
QLabel[role="fieldLabel"] {{
    font-size: 12px; font-weight: 600; color: {TEXT_DIM};
}}
QLabel[role="hint"]  {{ font-size: 11.5px; color: {TEXT_FAINT}; }}
QLabel[role="error"] {{ font-size: 11.5px; color: {RED_HOVER}; }}

QLineEdit {{
    background: {FIELD_BG};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 12px;
    selection-background-color: {ACCENT_TEAL};
    selection-color: {TEXT};
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit:disabled {{ color: {TEXT_FAINT}; }}
QLineEdit[invalid="true"] {{ border-color: {RED}; }}

QComboBox {{
    background: {FIELD_BG};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 12px;
}}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 30px; }}
QComboBox::down-arrow {{ image: url({chevron}); width: 16px; height: 16px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TEXT};
    selection-background-color: {BORDER};
    selection-color: {ACCENT};
    padding: 4px;
}}

/* -- feed / scroll -------------------------------------------------------*/
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 4px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_FAINT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

#FeedName {{ font-size: 13px; font-weight: 600; }}
#FeedMeta {{ font-size: 12px; color: {TEXT_DIM}; }}
#FeedTime {{ font-size: 11px; color: {TEXT_FAINT}; }}

QToolTip {{
    background: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 5px 8px;
}}

/* -- menus (world switcher) ---------------------------------------------- */
QMenu {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 26px 8px 12px;
    border-radius: 6px;
    color: {TEXT};
    font-size: 13px;
}}
QMenu::item:selected {{ background: {BORDER}; }}
QMenu::item:disabled {{ color: {TEXT_FAINT}; }}
QMenu::separator {{ height: 1px; background: {BORDER_SOFT}; margin: 5px 8px; }}
QMenu::icon {{ padding-left: 8px; }}

/* -- checkboxes ------------------------------------------------------------ */
QCheckBox {{ font-size: 13px; spacing: 9px; }}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border-radius: 5px;
    border: 1px solid {BORDER};
    background: {FIELD_BG};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url({check});
}}

/* -- invite code box --------------------------------------------------------- */
QPlainTextEdit {{
    background: {FIELD_BG};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 10px;
    color: {ACCENT};
    font-family: Consolas, monospace;
    font-size: 11px;
    selection-background-color: {ACCENT_TEAL};
}}

#SettingsSection {{
    font-family: "{fonts.DISPLAY}";
    font-size: 11px; font-weight: 600; letter-spacing: 2px;
    color: {EMBER};
}}
"""


def apply(app: QApplication):
    app.setStyle("Fusion")
    fonts.load()
    font = QFont()
    font.setFamilies(["Segoe UI Variable Display", "Segoe UI"])
    font.setPointSizeF(9.5)
    app.setFont(font)
    app.setStyleSheet(build_qss())
