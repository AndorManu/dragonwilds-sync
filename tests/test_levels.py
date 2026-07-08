"""The level table, validated two independent ways: against every value read
from in-game panels, and against wiki spot checks."""

import pytest

from app.core import levels

# (current xp, level shown in the game's own panel) — screenshot ground truth.
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


def test_wiki_spot_checks():
    assert levels.MAX_LEVEL == 99
    assert levels.req_xp(2) == 33
    assert levels.req_xp(4) == 111
    assert levels.req_xp(32) == 6608
    assert levels.req_xp(50) == 40_594
    assert levels.req_xp(93) == 342_568
    assert levels.req_xp(94) == 395_129   # the endgame spike begins
    assert levels.req_xp(99) == 1_000_000


def test_xp_for_level_round_trips_every_level():
    for level in range(1, levels.MAX_LEVEL + 1):
        assert levels.level_for_xp(levels.xp_for_level(level)) == level, level


def test_one_xp_short_stays_below():
    for level in range(2, levels.MAX_LEVEL + 1):
        assert levels.level_for_xp(levels.req_xp(level) - 1) == level - 1, level


def test_table_is_strictly_monotonic():
    for a, b in zip(levels.REQ_TABLE, levels.REQ_TABLE[1:]):
        assert b > a


def test_nothing_is_estimated_anymore():
    assert not levels.is_estimated(99)


def test_clamping():
    assert levels.xp_for_level(0) == 0
    assert levels.xp_for_level(999) == 1_000_000
    assert levels.level_for_xp(-5) == 1
    assert levels.level_for_xp(10**9) == 99
