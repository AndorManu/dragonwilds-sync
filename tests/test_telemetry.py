"""Anonymous reports: on by default, off with one setting, never anything personal."""

import pytest

from app.core import telemetry


@pytest.fixture
def backend(monkeypatch):
    sent = []
    monkeypatch.setattr(telemetry, "ENDPOINT", "https://example.invalid/rest/v1/events")
    monkeypatch.setattr(telemetry, "API_KEY", "public-insert-only")
    monkeypatch.setattr(telemetry, "_post", sent.append)

    class Sync:   # run the "background" send inline so the test can see it
        def __init__(self, target, args, **kw):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)
    monkeypatch.setattr(telemetry.threading, "Thread", Sync)
    return sent


def test_on_by_default_once_the_pc_has_an_id(backend):
    cfg = {}
    assert telemetry.send(cfg, "push", "valheim", "2.1.0", result="pushed") is None  # no id yet
    assert telemetry.ensure_id(cfg) and not telemetry.ensure_id(cfg)
    assert telemetry.send(cfg, "push", "valheim", "2.1.0", result="pushed") is not None


def test_nothing_is_sent_when_switched_off(backend):
    assert telemetry.send({"telemetry": False, "install_id": "a" * 32}, "push") is None
    assert backend == []


def test_nothing_is_sent_without_a_backend(monkeypatch):
    monkeypatch.setattr(telemetry, "ENDPOINT", "")
    cfg = {}
    telemetry.opt_in(cfg)
    assert telemetry.send(cfg, "push") is None


def test_opt_in_makes_a_random_id_and_sends(backend):
    cfg = {"player_name": "Andor"}
    telemetry.opt_in(cfg)
    assert len(cfg["install_id"]) == 32
    payload = telemetry.send(cfg, "push", "valheim", "2.0.0", result="pushed")
    assert backend == [payload]
    assert payload["game"] == "valheim" and payload["props"] == {"result": "pushed"}


def test_personal_data_never_gets_through(backend):
    cfg = {"player_name": "Andor"}
    telemetry.opt_in(cfg)
    payload = telemetry.send(cfg, "push", "valheim", "2.0.0", result="pushed",
                             world_name="Midgard", sync_dir="C:/Users/andor/Drive",
                             player="Andor", path="C:/secret")
    text = repr(payload)
    for leak in ("Midgard", "andor", "Andor", "secret"):
        assert leak not in text
    assert set(payload) == {"install_id", "app_version", "os", "game", "event", "props"}


def test_unknown_events_are_dropped(backend):
    cfg = {}
    telemetry.opt_in(cfg)
    assert telemetry.send(cfg, "keylogger") is None


def test_comment_is_trimmed(backend):
    cfg = {}
    telemetry.opt_in(cfg)
    payload = telemetry.send(cfg, "feedback", "raft", "2.0.0", rating="down",
                             comment="  " + "x" * 900)
    assert len(payload["props"]["comment"]) == telemetry.COMMENT_MAX


def test_opt_out_stops_sending(backend):
    cfg = {}
    telemetry.opt_in(cfg)
    telemetry.opt_out(cfg)
    assert telemetry.send(cfg, "push") is None
