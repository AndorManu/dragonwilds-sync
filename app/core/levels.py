"""The Dragonwilds skill level table — the game's own numbers, all 99 levels.

Source: the official wiki (dragonwilds.runescape.wiki/w/Experience), fetched
2026-07-09. Every one of the nine thresholds we independently read off
in-game skill panels matches this table exactly, which is as verified as it
gets. Notable: the cap was raised from 50 to 99, growth is ~10.35%/level up
to the low 90s, and levels 94-99 spike sharply (99 = exactly 1,000,000 XP).
"""

from bisect import bisect_right

# Total XP required to reach level L; index L-1. Levels 1..99.
REQ_TABLE = (
    0, 33, 70, 111, 156, 206, 261, 322, 389, 463,
    545, 636, 736, 847, 969, 1_104, 1_253, 1_417, 1_598, 1_798,
    2_018, 2_261, 2_529, 2_825, 3_152, 3_512, 3_910, 4_349, 4_833, 5_367,
    5_957, 6_608, 7_326, 8_118, 8_993, 9_958, 11_023, 12_199, 13_496, 14_929,
    16_510, 18_255, 20_181, 22_307, 24_654, 27_245, 30_105, 33_262, 36_747, 40_594,
    44_581, 48_717, 52_997, 57_421, 61_990, 66_702, 71_560, 76_562, 81_708, 86_998,
    92_433, 98_012, 103_735, 109_603, 115_616, 121_772, 128_073, 134_518, 141_108, 147_842,
    154_721, 161_743, 168_910, 176_222, 183_678, 191_278, 199_022, 206_911, 214_944, 223_122,
    231_444, 239_910, 248_521, 257_276, 266_176, 275_219, 284_407, 293_740, 303_217, 312_838,
    322_604, 332_514, 342_568, 395_129, 447_689, 543_044, 666_881, 819_200, 1_000_000,
)

MAX_LEVEL = len(REQ_TABLE)   # 99


def req_xp(level: int) -> int:
    """Total XP needed to reach `level` — exact, from the game's table."""
    level = max(1, min(int(level), MAX_LEVEL))
    return REQ_TABLE[level - 1]


def xp_for_level(level: int) -> int:
    """XP to write so a character lands exactly on `level`."""
    return req_xp(level)


def level_for_xp(xp: int) -> int:
    """The level a character with `xp` total is on."""
    xp = max(0, int(xp))
    return bisect_right(REQ_TABLE, xp)


def is_estimated(level: int) -> bool:
    """Kept for API compatibility: the whole table is exact now."""
    return False
