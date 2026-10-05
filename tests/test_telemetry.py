"""Anonymous reports: on by default, off with one setting, never anything personal."""

import json

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


def test_crash_report_has_type_and_function_but_no_message(backend):
    cfg = {}
    telemetry.opt_in(cfg)
    telemetry.set_context(cfg, "2.1.0")

    def load_world():
        raise KeyError("C:/Users/andor/secret/World.sav")
    try:
        load_world()
    except KeyError as e:
        payload = telemetry.send_crash(type(e), e.__traceback__)
    assert payload["event"] == "crash"
    assert payload["props"]["kind"] == "KeyError"
    assert "secret" not in repr(payload) and "andor" not in repr(payload)
    telemetry.set_context(None, "")


def test_forget_erases_and_gives_a_new_id(monkeypatch, backend):
    calls = []

    class Resp:
        def close(self):
            pass
    monkeypatch.setattr(telemetry.urllib.request, "urlopen",
                        lambda req, timeout: calls.append(json.loads(req.data)) or Resp())
    cfg = {}
    telemetry.opt_in(cfg)
    old = cfg["install_id"]
    assert telemetry.forget(cfg)
    assert calls == [{"p_install_id": old}]
    assert cfg["install_id"] != old and len(cfg["install_id"]) == 32


def test_new_numbers_and_labels_pass_the_whitelist(backend):
    cfg = {}
    telemetry.opt_in(cfg)
    p = telemetry.send(cfg, "push", "valheim", "2.1.0", result="pushed", sync_ms=812,
                       size_mb=12.345, files=3, group_size=4, duration_min=95,
                       cloud="google drive", world_name="Midgard")
    assert p["props"] == {"result": "pushed", "sync_ms": 812, "size_mb": 12.3, "files": 3,
                          "group_size": 4, "duration_min": 95, "cloud": "google drive"}
