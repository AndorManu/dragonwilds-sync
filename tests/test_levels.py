"""The level curve, validated against every value read from in-game panels."""

import pytest

from app.core import levels

# (current xp, level shown in the game's own panel) — the ground truth.
PANEL_TRUTH = [
    (6439, 31),   # Attack
    (100, 3),     # Magic
    (2989, 24),   # Ranged
    (2149, 21),   # Mining
    (5860, 30),   # Woodcutting
    (4433, 28),   # Artisan
    (2846, 24),   # Construction
    (772, 13),    # Cooking
    (1115, 16),   # Runecrafting
    (922, 14),    # Farming
    (0, 1),       # Fishing
]


@pytest.mark.parametrize("xp,expected_level", PANEL_TRUTH)
def test_level_for_xp_matches_the_game(xp, expected_level):
    assert levels.level_for_xp(xp) == expected_level


def test_known_thresholds_are_exact():
    assert levels.xp_for_level(32) == 6608
    assert levels.xp_for_level(31) == 5957
    assert levels.xp_for_level(25) == 3152
    assert levels.xp_for_level(4) == 111


def test_xp_for_level_round_trips_every_level():
    """Writing xp_for_level(L) must always classify back as exactly L."""
    for level in range(1, levels.MAX_LEVEL + 1):
        assert levels.level_for_xp(levels.xp_for_level(level)) == level, level


def test_req_is_strictly_monotonic():
    previous = -1
    for level in range(1, levels.MAX_LEVEL + 1):
        current = levels.req_xp(level)
        assert current > previous or level == 1, level
        previous = current


def test_margin_never_reaches_next_level():
    for level in range(2, levels.MAX_LEVEL):
        assert levels.xp_for_level(level) < levels.req_xp(level + 1), level


def test_estimated_flag():
    assert not levels.is_estimated(32)
    assert levels.is_estimated(33)


def test_clamping():
    assert levels.xp_for_level(0) == 0
    assert levels.xp_for_level(999) == levels.xp_for_level(levels.MAX_LEVEL)
    assert levels.level_for_xp(-5) == 1
    assert levels.level_for_xp(10**9) == levels.MAX_LEVEL
