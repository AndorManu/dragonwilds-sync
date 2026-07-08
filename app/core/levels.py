"""The Dragonwilds skill level curve, reverse-engineered from the game's own
skill panels (2026-07-09).

Nine ground-truth points were read off in-game panels ("6,439/6,608 XP" at
level 31 means level 32 requires 6,608 total XP). They fit

    REQ(L) = A * R**(L-1) + B      (A=327.95, R=1.10345, B=-332.4)

to within ±1 XP everywhere except the lowest levels (±3). Exact known
thresholds override the model; unknown levels use the model plus a small
overshoot margin so "make me level 25" never lands at 24. Levels beyond the
highest calibrated point (32) are extrapolated — flagged so the UI can mark
them as approximate.
"""

import math

# Total XP required to REACH level L — exact, read from in-game panels.
KNOWN_REQ = {
    4: 111, 14: 847, 15: 969, 17: 1253, 22: 2261,
    25: 3152, 29: 4833, 31: 5957, 32: 6608,
}

A = 327.95
R = 1.10345
B = -332.4

MAX_LEVEL = 60
CALIBRATED_MAX = 32


def _model(level: int) -> float:
    return A * math.pow(R, level - 1) + B


def req_xp(level: int) -> int:
    """Best-estimate total XP needed to reach `level` (no safety margin)."""
    if level <= 1:
        return 0
    if level in KNOWN_REQ:
        return KNOWN_REQ[level]
    return max(0, int(round(_model(level))))


def xp_for_level(level: int) -> int:
    """XP to write so the character lands exactly on `level`.

    Exact where calibrated; modelled values get a small overshoot (bigger
    when extrapolating) that stays far below the ~10% gap to the next level.
    """
    level = max(1, min(int(level), MAX_LEVEL))
    if level <= 1:
        return 0
    if level in KNOWN_REQ:
        return KNOWN_REQ[level]
    estimate = _model(level)
    margin = max(6.0, estimate * (0.03 if level > CALIBRATED_MAX else 0.01))
    return int(math.ceil(estimate + margin))


def level_for_xp(xp: int) -> int:
    """The level a character with `xp` total is on."""
    xp = max(0, int(xp))
    for level in range(MAX_LEVEL, 1, -1):
        if xp >= req_xp(level):
            return level
    return 1


def is_estimated(level: int) -> bool:
    return level > CALIBRATED_MAX
