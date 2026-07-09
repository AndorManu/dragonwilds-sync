"""Scroll of Knowledge and Gift Across the Void: union-merges, offerings,
and the safety contract (checkpoint-first, unknown fields untouched)."""

import json
from pathlib import Path

from app.core import backups, characters
from test_characters import make_character


def enrich(path: Path, recipes=(), spells=(), bitmap=None, mounts=()):
    """Give a fixture character some knowledge."""
    data = json.loads(path.read_text(encoding="utf-8"))
    progress = data["GameProgress"].setdefault("Progress", {})
    progress["RecipesUnlocked"] = list(recipes)
    progress["SpellsUnlocked"] = list(spells)
    data["GameProgress"].setdefault("Journal", {})["UnlockedEntries"] = []
    data["GameProgress"]["Character"].setdefault("Mount", {})[
        "MountsUnlockedList"] = list(mounts)
    if bitmap is not None:
        data["GameProgress"].setdefault("RevealedFog", {})[
            "RevealedRegionsBitmap"] = bitmap
    path.write_text(json.dumps(data, indent="\t"), encoding="utf-8")
    return data


def test_extract_and_counts(tmp_path):
    path = make_character(tmp_path, "Negrito")
    enrich(path, recipes=["r1", "r2", "r3"], spells=["s1"], bitmap=0b10111)
    data = json.loads(path.read_text(encoding="utf-8"))
    knowledge = characters.extract_knowledge(data)
    assert knowledge["recipes"] == ["r1", "r2", "r3"]
    assert knowledge["map_bitmap"] == 0b10111
    counts = characters.knowledge_counts(data)
    assert counts["recipes"] == 3
    assert counts["map_regions"] == 4


def test_scroll_roundtrip_and_absorb(tmp_path):
    teacher = make_character(tmp_path / "a", "Sage")
    enrich(teacher, recipes=["r1", "r2", "r3"], spells=["s1", "s2"], bitmap=0b0111)
    student = make_character(tmp_path / "b", "Novice")
    enrich(student, recipes=["r2", "r9"], spells=[], bitmap=0b1000)

    scroll_file = characters.write_scroll(teacher, tmp_path / "s" / "sage.scroll.json",
                                          "Andor")
    payload = characters.read_scroll(scroll_file)
    assert payload["author"] == "Andor"

    student_data = json.loads(student.read_text(encoding="utf-8"))
    gains = characters.diff_knowledge(student_data, payload["knowledge"])
    assert gains["recipes"] == 2          # r1, r3 are new; r2 already known
    assert gains["spells"] == 2
    assert gains["map_regions"] == 3      # 0b0111 adds three bits to 0b1000

    applied = characters.absorb_knowledge(student, payload["knowledge"],
                                          tmp_path / "bk")
    assert applied == gains
    after = json.loads(student.read_text(encoding="utf-8"))
    assert after["GameProgress"]["Progress"]["RecipesUnlocked"] == \
        ["r2", "r9", "r1", "r3"]          # union, original order preserved
    assert after["GameProgress"]["RevealedFog"]["RevealedRegionsBitmap"] == 0b1111
    assert after["Backup"] == 1675531120  # untouched, as always
    # checkpoint was taken before the merge
    assert len(backups.list_checkpoints(tmp_path / "bk")) == 1


def test_absorb_nothing_new_is_a_noop(tmp_path):
    path = make_character(tmp_path, "Solo")
    enrich(path, recipes=["r1"], bitmap=0b1)
    before = path.read_bytes()
    data = json.loads(path.read_text(encoding="utf-8"))
    gains = characters.absorb_knowledge(
        path, {"recipes": ["r1"], "map_bitmap": 0b1}, tmp_path / "bk")
    assert gains == {}
    assert path.read_bytes() == before
    assert backups.list_checkpoints(tmp_path / "bk") == []


def test_inventory_listing_and_free_slot(tmp_path):
    path = make_character(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    slots, max_index = characters.list_inventory(data)
    assert [s.index for s in slots] == [0, 8]
    assert max_index == 80
    assert slots[1].count == 99
    assert characters.first_free_slot(data) == 1


def test_new_item_guid_format():
    seen = {characters.new_item_guid() for _ in range(50)}
    assert len(seen) == 50
    for guid in seen:
        assert len(guid) == 22
        assert all(c.isalnum() or c in "-_" for c in guid)


def test_offering_and_gift(tmp_path):
    giver = make_character(tmp_path / "g", "Rich")
    receiver = make_character(tmp_path / "r", "Poor")

    offer_file = characters.export_offering(giver, tmp_path / "o" / "rich.gift.json",
                                            "Bram")
    offering = characters.read_offering(offer_file)
    assert offering["author"] == "Bram"
    assert len(offering["items"]) == 2

    stack = next(i for i in offering["items"] if i.get("Count"))
    slot_used = characters.receive_gift(receiver, stack, tmp_path / "bk")
    assert slot_used == 1                 # first free slot in the fixture

    after = json.loads(receiver.read_text(encoding="utf-8"))
    placed = after["GameProgress"]["Inventory"]["1"]
    assert placed["ItemData"] == stack["ItemData"]
    assert placed["Count"] == stack["Count"]
    # fresh GUID, not the giver's
    giver_data = json.loads(giver.read_text(encoding="utf-8"))
    giver_guids = {s.guid for s in characters.list_inventory(giver_data)[0]}
    assert placed["GUID"] not in giver_guids
    assert len(backups.list_checkpoints(tmp_path / "bk")) == 1


def test_gift_refused_when_bag_full(tmp_path):
    path = make_character(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    inventory = data["GameProgress"]["Inventory"]
    for i in range(81):
        inventory.setdefault(str(i), {"GUID": f"g{i}", "ItemData": "x", "Count": 1})
    path.write_text(json.dumps(data, indent="\t"), encoding="utf-8")
    assert characters.receive_gift(path, {"ItemData": "y", "Count": 1},
                                   tmp_path / "bk") is None


def test_editplan_per_item_repair(tmp_path):
    path = make_character(tmp_path)
    plan = characters.EditPlan(item_repairs={"0"})
    changes = characters.apply_edits(path, plan, tmp_path / "bk")
    assert any("repaired" in c for c in changes)
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["GameProgress"]["Inventory"]["0"]["Durability"] == characters.REPAIR_VALUE
    assert after["GameProgress"]["Inventory"]["8"]["Count"] == 99  # untouched
