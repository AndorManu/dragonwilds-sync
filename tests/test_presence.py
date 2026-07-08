"""Presence + turn-claim files: advisory, stale-tolerant, fail-soft."""

import json
from datetime import datetime, timedelta, timezone

from app.core import presence


def old_ts(hours):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")


def test_start_and_stop_playing(tmp_path):
    presence.start_playing(tmp_path, "Andor", "🐉")
    who = presence.who_is_playing(tmp_path)
    assert who["player"] == "Andor"
    assert who["emoji"] == "🐉"
    assert who["age_s"] < 60
    presence.stop_playing(tmp_path, "Andor")
    assert presence.who_is_playing(tmp_path) is None


def test_stop_playing_never_clears_someone_elses_marker(tmp_path):
    presence.start_playing(tmp_path, "Bram")
    presence.stop_playing(tmp_path, "Andor")
    assert presence.who_is_playing(tmp_path)["player"] == "Bram"


def test_stale_presence_ignored(tmp_path):
    (tmp_path / presence.PLAYING_NAME).write_text(
        json.dumps({"player": "Bram", "since": old_ts(5)}))
    assert presence.who_is_playing(tmp_path) is None


def test_corrupt_presence_ignored(tmp_path):
    (tmp_path / presence.PLAYING_NAME).write_text("{not json")
    assert presence.who_is_playing(tmp_path) is None


def test_missing_folder_fails_soft(tmp_path):
    gone = tmp_path / "nope"
    assert presence.who_is_playing(gone) is None
    presence.stop_playing(gone, "Andor")  # must not raise


def test_turn_claim_lifecycle(tmp_path):
    presence.claim_next(tmp_path, "Elise")
    assert presence.who_has_next(tmp_path)["player"] == "Elise"
    # someone else's clear with player guard does nothing
    presence.clear_next(tmp_path, "Andor")
    assert presence.who_has_next(tmp_path)["player"] == "Elise"
    presence.clear_next(tmp_path, "Elise")
    assert presence.who_has_next(tmp_path) is None


def test_stale_turn_claim_ignored(tmp_path):
    (tmp_path / presence.NEXT_NAME).write_text(
        json.dumps({"player": "Bram", "since": old_ts(13)}))
    assert presence.who_has_next(tmp_path) is None
