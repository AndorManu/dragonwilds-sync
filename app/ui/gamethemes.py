"""Every game gets its own look: palette, typefaces and banner scene.

A theme is a handful of base colours; the hover / pressed / surface shades
are derived so each one stays internally consistent. Text greys are shared
by every theme on purpose - legibility shouldn't change with the game.

Typefaces are the bundled Cinzel family plus fonts that ship with every
Windows 10/11 install, so nothing extra has to be downloaded.
"""

import colorsys
from dataclasses import dataclass, field


def _rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(r: float, g: float, b: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, round(c * 255))) for c in (r, g, b)))


def shade(hex_color: str, light: float = 0.0, sat: float = 0.0) -> str:
    """Shift lightness/saturation in HLS space (-1..1 steps, clamped)."""
    h, l, s = colorsys.rgb_to_hls(*_rgb(hex_color))
    return _hex(*colorsys.hls_to_rgb(h, max(0, min(1, l + light)), max(0, min(1, s + sat))))


def rgba(hex_color: str, alpha: float) -> str:
    r, g, b = (round(c * 255) for c in _rgb(hex_color))
    return f"rgba({r}, {g}, {b}, {alpha})"


@dataclass(frozen=True)
class GameTheme:
    id: str
    bg: str               # window base
    surface: str          # cards
    accent: str           # the "go / play" colour
    accent2: str          # gradient partner for the primary button
    on_accent: str        # text on the accent
    ember: str            # identity colour: section labels, flourishes
    gold_text: str        # legible warm text over art
    display: str          # titles and section labels
    deco: str             # hero world name
    voice: str            # flavour lines
    scene: str            # banner painter in scenes.py
    title_spacing: int = 3
    caps: bool = True     # display text in capitals
    overrides: dict = field(default_factory=dict, hash=False, compare=False)

    # derived ---------------------------------------------------------------
    def tokens(self) -> dict[str, str]:
        return {
            "BG": self.bg,
            "BG_HI": shade(self.bg, 0.035, 0.05),
            "BG_LO": shade(self.bg, -0.03),
            "SURFACE": self.surface,
            "SURFACE_2": shade(self.surface, 0.035),
            "SURFACE_GLASS": rgba(shade(self.surface, 0.04), 0.74),
            "FIELD_BG": shade(self.surface, -0.025),
            "BORDER": shade(self.surface, 0.07),
            "BORDER_SOFT": shade(self.surface, 0.035),
            "BORDER_GOLD": shade(self.ember, -0.32, -0.3),
            "ACCENT": self.accent,
            "ACCENT_HOVER": shade(self.accent, 0.07),
            "ACCENT_PRESSED": shade(self.accent, -0.09),
            "ACCENT_TEAL": self.accent2,
            "ACCENT_TEAL_HI": shade(self.accent2, 0.07),
            "ACCENT_TEAL_LO": shade(self.accent2, -0.09),
            "ON_ACCENT": self.on_accent,
            "EMBER": self.ember,
            "EMBER_HI": shade(self.ember, 0.1),
            "EMBER_DEEP": shade(self.ember, -0.12),
            "EMBER_PRESSED": shade(self.ember, -0.2),
            "GOLD_TEXT": self.gold_text,
        } | self.overrides


THEMES: dict[str, GameTheme] = {t.id: t for t in (
    # WorldSync's own home: deep ink with a cool signal blue and a warm spark.
    GameTheme("library", bg="#0A0C14", surface="#121624", accent="#7A9BFF",
              accent2="#5CD6C9", on_accent="#070B1A", ember="#F2B66B",
              gold_text="#E9D7B8", display="Bahnschrift SemiBold",
              deco="Bahnschrift SemiBold", voice="Georgia", scene="library",
              title_spacing=4),
    # The original look, unchanged.
    GameTheme("dragonwilds", bg="#0A0D12", surface="#12191F", accent="#3ECF8E",
              accent2="#1FA89B", on_accent="#07130D", ember="#E8A23D",
              gold_text="#E6C892", display="Cinzel", deco="Cinzel Decorative",
              voice="EB Garamond", scene="dragonwilds",
              overrides={"BG_HI": "#10161E", "BG_LO": "#070A0E", "SURFACE_2": "#1A232C",
                         "SURFACE_GLASS": "rgba(22, 30, 39, 0.72)", "FIELD_BG": "#0D131A",
                         "BORDER": "#222E39", "BORDER_SOFT": "#19222C",
                         "BORDER_GOLD": "#3A3223", "ACCENT_HOVER": "#55DCA0",
                         "ACCENT_PRESSED": "#29A872", "ACCENT_TEAL_HI": "#23BCAD",
                         "ACCENT_TEAL_LO": "#17897E", "EMBER_HI": "#F6C56A",
                         "EMBER_DEEP": "#B9761F", "EMBER_PRESSED": "#8F5A16"}),
    # Aurora over the tenth world; bronze for the runes.
    GameTheme("valheim", bg="#080D12", surface="#101920", accent="#55D6B4",
              accent2="#3A9FC4", on_accent="#04140F", ember="#C99A55",
              gold_text="#E2CFA8", display="Cinzel", deco="Cinzel",
              voice="Constantia", scene="valheim", title_spacing=5),
    # The Shroud: violet fog against a flame.
    GameTheme("enshrouded", bg="#0C0A12", surface="#16121F", accent="#B88CFF",
              accent2="#7C5BE0", on_accent="#120A21", ember="#FF8F4A",
              gold_text="#F0D2B6", display="Georgia", deco="Georgia",
              voice="Georgia", scene="enshrouded", caps=False, title_spacing=1),
    # Bright, round and friendly: sky blue and sunshine.
    GameTheme("palworld", bg="#0A1018", surface="#111B27", accent="#4DBBFF",
              accent2="#2F8CFF", on_accent="#04121F", ember="#FFD447",
              gold_text="#FFE8A3", display="Segoe UI Black", deco="Segoe UI Black",
              voice="Segoe UI", scene="palworld", caps=False, title_spacing=0),
    # Glowing core crystals in a dark cave; pixel scene, monospace type.
    GameTheme("core_keeper", bg="#090B10", surface="#12151D", accent="#5FE3F2",
              accent2="#3C9BE6", on_accent="#031418", ember="#FFB54D",
              gold_text="#F3D9A8", display="Consolas", deco="Consolas",
              voice="Consolas", scene="core_keeper", title_spacing=2),
    # Survival horror: blood and bone among the pines.
    GameTheme("sons_of_the_forest", bg="#0A0B0A", surface="#141614", accent="#D9493C",
              accent2="#9E2B24", on_accent="#FFF1EC", ember="#D8CBB0",
              gold_text="#E4DAC4", display="Bahnschrift SemiCondensed",
              deco="Bahnschrift SemiBold Condensed", voice="Georgia",
              scene="sons_of_the_forest", title_spacing=4),
    # Gothic: blood moon crimson and a royal violet.
    GameTheme("v_rising", bg="#0C080C", surface="#181019", accent="#E33A55",
              accent2="#9A2A5E", on_accent="#FFF0F3", ember="#A98BE8",
              gold_text="#E6D0E8", display="Cinzel", deco="Cinzel Decorative",
              voice="EB Garamond", scene="v_rising", title_spacing=4),
    # Backyard sunshine: leaf green and orange juice.
    GameTheme("grounded", bg="#0A0F09", surface="#121A10", accent="#93D640",
              accent2="#4FAE3A", on_accent="#0B1504", ember="#FFA53D",
              gold_text="#F6E1A6", display="Trebuchet MS", deco="Trebuchet MS",
              voice="Trebuchet MS", scene="grounded", caps=False, title_spacing=0),
    # Open water at sunset.
    GameTheme("raft", bg="#071017", surface="#0E1B24", accent="#33CFE0",
              accent2="#1E8FB8", on_accent="#03161B", ember="#FF8466",
              gold_text="#FFD9C4", display="Franklin Gothic Medium",
              deco="Franklin Gothic Medium", voice="Georgia", scene="raft",
              title_spacing=2),
    # Wasteland: rust, hazard yellow and a red sky.
    GameTheme("seven_days_to_die", bg="#0D0A08", surface="#1A1410", accent="#EE7A2F",
              accent2="#B8461E", on_accent="#1A0B03", ember="#E8C532",
              gold_text="#EAD9B0", display="Impact", deco="Impact",
              voice="Bahnschrift", scene="seven_days_to_die", title_spacing=3),
)}


def get(theme_id: str | None) -> GameTheme:
    return THEMES.get(theme_id or "library", THEMES["library"])
