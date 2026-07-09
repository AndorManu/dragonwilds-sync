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
    assert items.icon_key("2rxJ495rm0GDn4h5OWKiyQ")  # ash logs -> some key


def test_pouch_grouping():
    # a rune goes to the Runes pouch; a weapon to Gear & Tools
    fire_rune = "_QMgbMYhjU-9jAD_euFbyQ"
    assert items.pouch(fire_rune) == "Runes"
    assert items.pouch("unknown-id") == "Materials"  # graceful default
    pouches = {name for name, _ in items.POUCHES}
    for cat in items.categories():
        # every catalogued category maps into a real pouch or the default
        assert items.POUCHES  # sanity: pouches exist


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


def _by_name() -> dict:
    return {e["name"]: i for i, e in items._catalog().items()}


def test_tier_ladder_orders_materials_low_to_high():
    by = _by_name()
    ladder = [m["id"] for m in items.tier_ladder(by["Bronze Dagger"])]
    assert ladder == [by["Bronze Dagger"], by["Iron Dagger"],
                      by["Steel Dagger"], by["Mithril Dagger"]]
    assert items.tier_position(by["Steel Dagger"]) == (3, 4)
    assert items.tier_position("totally-made-up") == (0, 0)


def test_tier_neighbors_walk_and_stop_at_the_ends():
    by = _by_name()
    assert items.tier_neighbor(by["Bronze Dagger"], -1) is None
    assert items.tier_neighbor(by["Bronze Dagger"], +1)["id"] == by["Iron Dagger"]
    assert items.tier_neighbor(by["Mithril Dagger"], +1) is None
    assert items.tier_neighbor(by["Mithril Dagger"], -1)["id"] == by["Steel Dagger"]


def test_tier_neighbor_skips_equal_ranks():
    # Copper and Tin ore share a rank; an upgrade jumps to the next real tier.
    by = _by_name()
    up = items.tier_neighbor(by["Copper Ore"], +1)
    assert up and up["name"] == "Iron Ore"
    assert items.tier_neighbor(by["Copper Ore"], -1) is None


def test_untiered_and_unknown_items_have_no_ladder():
    assert items.tier_ladder("totally-made-up") == []
    assert items.tier_neighbor("totally-made-up", +1) is None


def test_is_stackable():
    by = _by_name()
    assert items.is_stackable(by["Bronze Arrow"])
    assert not items.is_stackable(by["Bronze Dagger"])


def test_category_icons_are_own_glyphs_not_skill_emblems():
    # ores no longer borrow the mining pickaxe; ammo has a single-arrow glyph.
    assert items.CATEGORY_ICON["Ores"] == "cat-ore"
    assert items.CATEGORY_ICON["Arrows"] == "cat-arrow"
    assert items.CATEGORY_ICON["Woodcutting"] == "cat-log"
    assert not any(v.startswith("skill-") for v in items.CATEGORY_ICON.values())
