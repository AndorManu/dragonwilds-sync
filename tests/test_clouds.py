"""Join-flow folder matching: right name, right world, wrong ones rejected."""

import json

from app.core import clouds, paths


def fake_roots(monkeypatch, *roots):
    monkeypatch.setattr(clouds, "detect_cloud_roots",
                        lambda: [("Test Drive", r) for r in roots])


def test_finds_folder_by_name(tmp_path, monkeypatch):
    (tmp_path / "Dragonwilds Sync").mkdir()
    fake_roots(monkeypatch, tmp_path)
    found = clouds.find_synced_folder("Dragonwilds Sync", "Minhalla")
    assert found == tmp_path / "Dragonwilds Sync"


def test_matching_manifest_accepted(tmp_path, monkeypatch):
    folder = tmp_path / "DW"
    folder.mkdir()
    (folder / paths.MANIFEST_NAME).write_text(
        json.dumps({"version": 3, "world_name": "Minhalla"}))
    fake_roots(monkeypatch, tmp_path)
    assert clouds.find_synced_folder("DW", "Minhalla") == folder


def test_wrong_world_manifest_rejected(tmp_path, monkeypatch):
    folder = tmp_path / "DW"
    folder.mkdir()
    (folder / paths.MANIFEST_NAME).write_text(
        json.dumps({"version": 3, "world_name": "SomeOtherWorld"}))
    fake_roots(monkeypatch, tmp_path)
    assert clouds.find_synced_folder("DW", "Minhalla") is None


def test_missing_folder_returns_none(tmp_path, monkeypatch):
    fake_roots(monkeypatch, tmp_path)
    assert clouds.find_synced_folder("Nope", "Minhalla") is None


def test_second_root_searched(tmp_path, monkeypatch):
    root1 = tmp_path / "r1"
    root2 = tmp_path / "r2"
    root1.mkdir()
    (root2 / "DW").mkdir(parents=True)
    fake_roots(monkeypatch, root1, root2)
    assert clouds.find_synced_folder("DW", None) == root2 / "DW"
