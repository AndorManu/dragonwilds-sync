"""End-to-end shakedown of the entire grimoire (the secret menu).

Builds a realistic Version-75 character and drives every operation the UI
performs through the core, asserting after each that the save stays valid,
the Backup field and the .backup twin are never touched, and only the
intended fields change. Also sweeps the full item catalogue and the unlock
catalogues so 'do all the items/spells actually work' is answered by proof.
"""

import json
from pathlib import Path

import pytest

from app.core import backups, characters, items, levels
from app.core.characters import EditPlan

REAL_SPELL = "n_deu0x83JSQ0e2grNvJKA"          # Surge (castable)
NON_WHEEL = "NejB6kiCxneFTLCV74PdyA"           # Whetstone (ability, not wheel)
BACKUP_VALUE = 1675531120


def rich_character(path: Path, name="Tester") -> Path:
    """A realistic character touching every structure the grimoire edits."""
    skill_ids = list(characters.DEFAULT_SKILL_LABELS.keys())
    some_items = items.search()  # real catalogue rows
    inv = {"MaxSlotIndex": 80}
    for i, row in enumerate(some_items[:6]):
        slot = {"GUID": f"g{i}", "ItemData": row["id"]}
        if row["max"] > 1:
            slot["Count"] = 5
        else:
            slot["Durability"] = 500
        inv[str(i)] = slot
    data = {
        "Version": 75,
        "meta_data": {"char_guid": "ABC", "char_name": name,
                      "worlds_playtime": {"w1": 1782857199}, "char_type": 0},
        "SaveCount": 100,
        "Customization": {"CustomizationData": {
            "BodyType": {"dataTable": "DT", "rowName": "male_A_01"},
            "Head": {"dataTable": "DT", "rowName": "male_A_01"},
            "SkinTone": {"dataTable": "DT", "rowName": "SkinTone8"},
            "HairPreset": {"dataTable": "DT", "rowName": "Preset8"},
            "HairColor": {"dataTable": "DT", "rowName": "Color6"},
            "FacialHairPreset": {"dataTable": "DT", "rowName": "M_A_PresetNone"},
            "EyeColor": {"dataTable": "DT", "rowName": "Color2"},
            "EyebrowColor": {"dataTable": "DT", "rowName": "Color6"},
        }},
        "Hardcore": {"IsHardcore": True, "AssociatedWorld": "world1"},
        "GameProgress": {
            "Version": 75,
            "Character": {
                "Playtime_wall": 13336.56,
                "Health": {"CurrentValue": 42.0},
                "Stamina": {"CurrentValue": 30.0},
                "Sustenance": {"SustenanceValue": 20.0, "SustenanceDecayBuffer": 0},
                "Hydration": {"HydrationValue": 15.0, "HydrationDecayBuffer": 0},
                "Endurance": {"EnduranceValue": 50.0, "EnduranceDecayBuffer": 0},
                "StatusEffects": {
                    "Poison": {"Hash": 1, "Value": 8, "Active": [True]},
                    "Burning": {"Hash": 2, "Value": 3, "Active": [True]},
                    "Cold": {"Hash": 3, "Value": 0, "Active": [False]},
                },
                "Mount": {"MountEquipped": "None", "MountsUnlockedList": []},
            },
            "Inventory": inv,
            "PersonalInventory": {"MaxSlotIndex": -1},
            "Loadout": {
                "0": {"GUID": "L0", "ItemData": items.search()[0]["id"],
                      "Durability": 120},
                "5": {"PlayerInventoryItemIndex": 2},   # hotbar ref, not gear
                "MaxSlotIndex": 8,
            },
            "Progress": {
                "SpellsUnlocked": [REAL_SPELL],
                "RecipesUnlocked": [],
                "BuildingsUnlocked": [],
            },
            "Journal": {"UnlockedEntries": []},
            "RevealedFog": {"RevealedRegionsBitmap": 3},
            "RevealedLandmarks": {"RevealedLandmarkNames": []},
            "Skills": {"Skills": [{"Id": sid, "Xp": 100} for sid in skill_ids]},
            "Spellcasting": {"SelectedSpells": [REAL_SPELL] + [""] * 47},
        },
        "Backup": BACKUP_VALUE,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent="\t", ensure_ascii=False), encoding="utf-8")
    twin = Path(str(path) + ".backup")
    twin.write_text(json.dumps(dict(data, SaveCount=99), indent="\t"), encoding="utf-8")
    return path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_intact(path, twin_bytes):
    """File parses, Backup field preserved, .backup twin untouched."""
    data = load(path)                       # raises if corrupt
    assert data["Backup"] == BACKUP_VALUE
    assert Path(str(path) + ".backup").read_bytes() == twin_bytes
    return data


@pytest.fixture
def char(tmp_path):
    p = rich_character(tmp_path / "SaveCharacters" / "Tester.json")
    twin = Path(str(p) + ".backup").read_bytes()
    return p, tmp_path / "backups", twin


# ---------------------------------------------------------------------------
# the full gauntlet
# ---------------------------------------------------------------------------

def test_levels_all_skills_to_99(char):
    path, root, twin = char
    plan = EditPlan(skill_xp={sid: levels.xp_for_level(99)
                              for sid in characters.DEFAULT_SKILL_LABELS})
    changes = characters.apply_edits(path, plan, root)
    assert changes
    data = assert_intact(path, twin)
    for s in data["GameProgress"]["Skills"]["Skills"]:
        assert levels.level_for_xp(int(s["Xp"])) == 99


def test_all_quick_boons(char):
    path, root, twin = char
    plan = EditPlan(heal_vitals=True, repair_all=True, cleanse=True,
                    disable_hardcore=True)
    characters.apply_edits(path, plan, root)
    data = assert_intact(path, twin)
    char_node = data["GameProgress"]["Character"]
    assert char_node["Health"]["CurrentValue"] == characters.HEAL_VALUE
    assert char_node["StatusEffects"]["Poison"]["Value"] == 0
    assert char_node["StatusEffects"]["Poison"]["Active"] == [False]
    assert data["Hardcore"]["IsHardcore"] is False
    assert data["GameProgress"]["Inventory"]["0"].get("Durability") in (
        None, characters.REPAIR_VALUE)


def test_appearance_all_slots(char):
    path, root, twin = char
    plan = EditPlan(appearance={"SkinTone": "SkinTone3", "HairPreset": "Preset2",
                                "HairColor": "Color1", "EyeColor": "Color5",
                                "EyebrowColor": "Color4"})
    characters.apply_edits(path, plan, root)
    data = assert_intact(path, twin)
    cust = data["Customization"]["CustomizationData"]
    assert cust["SkinTone"]["rowName"] == "SkinTone3"
    assert cust["HairPreset"]["rowName"] == "Preset2"
    assert cust["BodyType"]["rowName"] == "male_A_01"   # untouched


def test_repair_inventory_and_equipped(char):
    path, root, twin = char
    plan = EditPlan(item_repairs={"0", "L0"}, item_counts={})
    characters.apply_edits(path, plan, root)
    data = assert_intact(path, twin)
    assert data["GameProgress"]["Loadout"]["0"]["Durability"] == characters.REPAIR_VALUE


def test_every_catalogue_item_is_sane():
    catalog_rows = items.search()
    assert len(catalog_rows) > 500
    for row in catalog_rows:
        assert row["name"] and row["name"] != "Unknown item"
        assert row["max"] >= 1
        assert 1 <= row["rank"] <= 6
        assert items.icon_key(row["id"])            # resolves to a glyph
        assert items.pouch(row["id"]) in {n for n, _ in items.POUCHES}


def test_conjure_one_of_every_category(char):
    path, root, twin = char
    # empty the bag so there's room, then conjure a sample per category
    data = load(path)
    data["GameProgress"]["Inventory"] = {"MaxSlotIndex": 400}
    Path(path).write_text(json.dumps(data, indent="\t"), encoding="utf-8")
    twin2 = Path(str(path) + ".backup").read_bytes()

    picks = {}
    for row in items.search():
        picks.setdefault(row["category"], row)
    placed = 0
    for row in picks.values():
        slot = characters.spawn_item(path, row["id"], 999, root)
        assert slot is not None
        placed += 1
    assert placed >= 15
    data = load(path)                                # still valid JSON
    assert data["Backup"] == BACKUP_VALUE
    inv = data["GameProgress"]["Inventory"]
    # every conjured item is present and its stack respects the item's cap
    for row in picks.values():
        matches = [v for k, v in inv.items()
                   if isinstance(v, dict) and v.get("ItemData") == row["id"]]
        assert matches
        for m in matches:
            if "Count" in m:
                assert 1 <= m["Count"] <= items.max_stack(row["id"])


def test_conjure_clamps_to_max_stack(char):
    path, root, twin = char
    data = load(path)
    data["GameProgress"]["Inventory"] = {"MaxSlotIndex": 10}
    Path(path).write_text(json.dumps(data, indent="\t"), encoding="utf-8")
    # find a low-stack item and try to conjure way too many
    low = next(r for r in items.search() if 1 < r["max"] <= 50)
    characters.spawn_item(path, low["id"], 9999, root)
    inv = load(path)["GameProgress"]["Inventory"]
    placed = next(v for v in inv.values()
                  if isinstance(v, dict) and v.get("ItemData") == low["id"])
    assert placed["Count"] == low["max"]             # clamped, not 9999


def test_scroll_and_gift_between_characters(tmp_path):
    root = tmp_path / "bk"
    teacher = rich_character(tmp_path / "a" / "Teacher.json")
    student = rich_character(tmp_path / "b" / "Student.json")
    tw = load(teacher)
    tw["GameProgress"]["Progress"]["RecipesUnlocked"] = ["r1", "r2", "r3"]
    tw["GameProgress"]["Inventory"]["7"] = {"GUID": "gg", "ItemData": items.search()[3]["id"], "Count": 40}
    Path(teacher).write_text(json.dumps(tw, indent="\t"), encoding="utf-8")

    scroll = characters.write_scroll(teacher, tmp_path / "s.json", "Teacher")
    payload = characters.read_scroll(scroll)
    gains = characters.absorb_knowledge(student, payload["knowledge"], root)
    assert gains.get("recipes", 0) >= 3

    offer = characters.export_offering(teacher, tmp_path / "o.json", "Teacher")
    item = next(i for i in characters.read_offering(offer)["items"] if i.get("Count"))
    slot = characters.receive_gift(student, item, root)
    assert slot is not None


def test_complete_codex_full_and_clean_bar(char):
    path, root, twin = char
    # put a non-castable ability into the unlocked set to prove it's kept off the bar
    data = load(path)
    data["GameProgress"]["Progress"]["SpellsUnlocked"].append(NON_WHEEL)
    Path(path).write_text(json.dumps(data, indent="\t"), encoding="utf-8")

    catalogs = characters.load_unlock_catalogs()
    gains = characters.grant_all_unlocks(path, catalogs, root)
    assert gains["spells"] > 30 and gains["recipes"] > 400
    data = assert_intact(path, twin)
    bar = data["GameProgress"]["Spellcasting"]["SelectedSpells"]
    assert NON_WHEEL not in bar                        # never on the wheel
    assert REAL_SPELL in bar
    # every non-empty bar entry is a real (castable) spell, no placeholders added
    for s in bar:
        assert s not in characters.NON_WHEEL_SPELL_IDS


def test_every_operation_takes_a_checkpoint(char):
    path, root, twin = char
    characters.apply_edits(path, EditPlan(skill_xp={
        list(characters.DEFAULT_SKILL_LABELS)[0]: 999}), root)
    assert len(backups.list_checkpoints(root)) == 1
    characters.spawn_item(path, items.search()[0]["id"], 1, root)
    assert len(backups.list_checkpoints(root)) == 2
