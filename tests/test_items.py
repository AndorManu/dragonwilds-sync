"""The bundled item catalogue and the conjuring spawn."""

import json

from app.core import characters, items
from test_characters import make_character


def test_catalogue_loads_and_is_substantial():
    cats = items.categories()
    assert len(items._catalog()) > 500
    assert "Melee Weapons" in cats
    assert "Food" in cats


def test_known_items_resolve():
    # Ash logs — a stable, low-tier resource present since launch
    ash = "2rxJ495rm0GDn4h5OWKiyQ"
    assert items.known(ash)
    assert "ash" in items.name(ash).lower()
    assert items.name(ash) != "Unknown item"
    assert items.max_stack(ash) >= 2
    label, color = items.rarity(ash)
    assert label in {r[0] for r in items.RARITY.values()}
    assert color.startswith("#")


def test_unknown_item_is_graceful():
    assert not items.known("totally-made-up")
    assert items.name("totally-made-up") == "Unknown item"
    assert items.max_stack("totally-made-up") == 9999
    assert items.rarity("totally-made-up")[0] == "Common"


def test_search_by_category_and_rarity():
    weapons = items.search(category_filter="Melee Weapons")
    assert weapons and all(r["category"] == "Melee Weapons" for r in weapons)
    # sorted by rarity descending
    ranks = [r["rank"] for r in weapons]
    assert ranks == sorted(ranks, reverse=True)
    legendary = items.search(min_rank=6)
    assert all(r["rank"] >= 6 for r in legendary)


def test_search_by_text():
    rows = items.search("bronze")
    assert rows and all("bronze" in r["name"].lower() for r in rows)


def test_icon_key_maps_categories():
    assert items.CATEGORY_ICON["Melee Weapons"] == "cat-sword"
    assert items.icon_key("2rxJ495rm0GDn4h5OWKiyQ")  # ash wood -> some key


def test_spawn_item_into_free_slot(tmp_path):
    path = make_character(tmp_path)
    ash = "2rxJ495rm0GDn4h5OWKiyQ"
    slot = characters.spawn_item(path, ash, 40, tmp_path / "bk")
    assert slot == 1   # first free slot in the fixture
    data = json.loads(path.read_text(encoding="utf-8"))
    placed = data["GameProgress"]["Inventory"]["1"]
    assert placed["ItemData"] == ash
    assert placed["Count"] == 40
    assert len(placed["GUID"]) == 22
    from app.core import backups
    assert len(backups.list_checkpoints(tmp_path / "bk")) == 1


def test_spawn_respects_backup_and_unknowns(tmp_path):
    path = make_character(tmp_path, backup_value=53184729)
    before = json.loads(path.read_text(encoding="utf-8"))
    characters.spawn_item(path, "2rxJ495rm0GDn4h5OWKiyQ", 1, tmp_path / "bk")
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["Backup"] == 53184729
    assert after["meta_data"] == before["meta_data"]
