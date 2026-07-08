"""Backup browser: listing and reversible restore."""

from app.core.backups import list_backups, restore_backup
from app.core.sync import _backup_files

WORLD = "Minhalla"


def make_save(folder, content):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{WORLD}.sav").write_bytes(content.encode())
    (folder / f"{WORLD}.sav.backup").write_bytes((content + "-b").encode())


def test_list_backups_newest_first_with_labels(tmp_path):
    saves = tmp_path / "saves"
    root = tmp_path / "backups"
    make_save(saves, "one")
    files = sorted(saves.glob("*"))
    _backup_files(files, "local_v3", root)
    _backup_files(files, "shared_v4", root)

    infos = list_backups(root)
    assert len(infos) == 2
    assert infos[0].label in ("local_v3", "shared_v4")
    assert all(i.file_count == 2 for i in infos)
    assert all(i.stamp is not None for i in infos)
    names = [i.path.name for i in infos]
    assert names == sorted(names, reverse=True)


def test_list_backups_empty_or_missing(tmp_path):
    assert list_backups(tmp_path / "nope") == []


def test_restore_replaces_saves_and_keeps_a_pre_restore_backup(tmp_path):
    saves = tmp_path / "saves"
    root = tmp_path / "backups"
    make_save(saves, "old-glory")
    _backup_files(sorted(saves.glob("*")), "local_v3", root)

    make_save(saves, "current")
    backup = list_backups(root)[0]
    restored = restore_backup(backup.path, saves, WORLD, root)

    assert restored == 2
    assert (saves / f"{WORLD}.sav").read_bytes() == b"old-glory"
    # what we replaced is itself recoverable
    pre = [i for i in list_backups(root) if i.label == "pre_restore"]
    assert len(pre) == 1
    assert (pre[0].path / f"{WORLD}.sav").read_bytes() == b"current"


def test_restore_empty_backup_is_a_noop(tmp_path):
    saves = tmp_path / "saves"
    make_save(saves, "current")
    empty = tmp_path / "backups" / "20260101-000000_local_v1"
    empty.mkdir(parents=True)
    assert restore_backup(empty, saves, WORLD, tmp_path / "backups") == 0
    assert (saves / f"{WORLD}.sav").read_bytes() == b"current"
