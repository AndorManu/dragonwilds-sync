"""Character parsing and the Dragon's Bargain editor.

The fixture replicates the verified structure of a real Version-75 character
file (tab-indented JSON, .backup twin, opaque Backup field).
"""

import json
from pathlib import Path

import pytest

from app.core import characters
from app.core.characters import EditPlan

SKILL_A = "4zYUGF5u_0KbMLkWJmmBbQ"
SKILL_B = "Wf3i7Ha-B06DH719j1vtBw"


def make_character(folder: Path, name="Negrito", backup_value=1675531120) -> Path:
    data = {
        "Version": 75,
        "meta_data": {
            "char_guid": "2FD6CC82473F21C514627F802A69C596",
            "worlds_playtime": {"7BF5835E4157DEC5": 1782857199,
                                "87660A394EC5C246": 1783347925},
            "char_name": name,
            "char_type": 0,
        },
        "SaveCount": 100,
        "Customization": {"CustomizationData": {
            "BodyType": {"dataTable": "DT", "rowName": "male_A_01"},
            "SkinTone": {"dataTable": "DT", "rowName": "SkinTone8"},
            "HairPreset": {"dataTable": "DT", "rowName": "Preset8"},
            "HairColor": {"dataTable": "DT", "rowName": "Color6"},
            "FacialHairPreset": {"dataTable": "DT", "rowName": "M_A_PresetNone"},
            "EyeColor": {"dataTable": "DT", "rowName": "Color2"},
        }},
        "GameProgress": {
            "Version": 75,
            "Character": {
                "Playtime_wall": 13336.56,
                "Health": {"CurrentValue": 122.5},
                "Stamina": {"CurrentValue": 100},
                "Sustenance": {"SustenanceValue": 65.34, "SustenanceDecayBuffer": 0},
                "Hydration": {"HydrationValue": 84.0, "HydrationDecayBuffer": 0},
                "Endurance": {"EnduranceValue": 99.9, "EnduranceDecayBuffer": 0},
            },
            "Inventory": {
                "0": {"GUID": "aaa", "ItemData": "xxx", "Durability": 736},
                "8": {"GUID": "bbb", "ItemData": "yyy", "Count": 99},
                "MaxSlotIndex": 80,
            },
            "Loadout": {
                "0": {"GUID": "ccc", "ItemData": "zzz", "Durability": 748},
                "MaxSlotIndex": 8,
            },
            "Skills": {"Skills": [
                {"Id": SKILL_A, "Xp": 5636},
                {"Id": SKILL_B, "Xp": 4433},
            ]},
        },
        "Backup": backup_value,
    }
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.json"
    path.write_text(json.dumps(data, indent="\t", ensure_ascii=False), encoding="utf-8")
    (folder / f"{name}.json.backup").write_text(
        json.dumps(dict(data, SaveCount=99), indent="\t"), encoding="utf-8")
    return path


def test_parse_character(tmp_path):
    path = make_character(tmp_path)
    info = characters.parse_character(path)
    assert info.name == "Negrito"
    assert info.playtime_s == pytest.approx(13336.56)
    assert info.health == pytest.approx(122.5)
    assert info.total_xp == 5636 + 4433
    assert len(info.skills) == 2
    assert info.inventory_slots == 2
    assert info.last_played is not None and info.last_played.year == 2026
    assert info.appearance["SkinTone"] == "SkinTone8"


def test_list_characters_sorted_and_weird_names(tmp_path):
    make_character(tmp_path, "Negrito")
    weird = make_character(tmp_path, "1⁧⁧Minblyat")  # real-world case
    assert weird.exists()
    infos = characters.list_characters(tmp_path)
    assert len(infos) == 2
    assert {i.name for i in infos} == {"Negrito", "1⁧⁧Minblyat"}


def test_portrait_descriptor_compact(tmp_path):
    info = characters.parse_character(make_character(tmp_path))
    desc = characters.portrait_descriptor(info)
    assert "SkinTone8" in desc and "Preset8" in desc
    assert len(desc) < 160


def test_cleanse_and_hardcore(tmp_path):
    path = make_character(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["Hardcore"] = {"IsHardcore": True, "AssociatedWorld": "x"}
    data["GameProgress"]["Character"]["StatusEffects"] = {
        "Poison": {"Hash": 1, "Value": 5, "Active": [True]},
        "Cold": {"Hash": 2, "Value": 0, "Active": [False]},
    }
    path.write_text(json.dumps(data, indent="\t"), encoding="utf-8")

    assert characters.is_hardcore(json.loads(path.read_text(encoding="utf-8")))
    assert characters.active_status_effects(
        json.loads(path.read_text(encoding="utf-8"))) == ["Poison"]

    characters.apply_edits(path, characters.EditPlan(cleanse=True,
                                                     disable_hardcore=True),
                           tmp_path / "bk")
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["Hardcore"]["IsHardcore"] is False
    assert after["GameProgress"]["Character"]["StatusEffects"]["Poison"]["Value"] == 0
    assert after["GameProgress"]["Character"]["StatusEffects"]["Poison"]["Active"] == [False]
    assert not characters.active_status_effects(after)


def test_appearance_edit(tmp_path):
    path = make_character(tmp_path)
    plan = characters.EditPlan(appearance={"SkinTone": "SkinTone3",
                                           "HairColor": "Color2"})
    changes = characters.apply_edits(path, plan, tmp_path / "bk")
    assert changes
    data = json.loads(path.read_text(encoding="utf-8"))
    cust = data["Customization"]["CustomizationData"]
    assert cust["SkinTone"]["rowName"] == "SkinTone3"
    assert cust["HairColor"]["rowName"] == "Color2"
    # a slot we didn't touch is unchanged
    assert cust["EyeColor"]["rowName"] == "Color2"


def test_list_loadout_equipped(tmp_path):
    path = make_character(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    equipped = characters.list_loadout(data)
    # fixture loadout has one real gear slot (durability) + hotbar-index refs
    assert any(s.durability is not None for s in equipped)
    assert all(s.item_data for s in equipped)


def test_repair_equipped_via_L_key(tmp_path):
    path = make_character(tmp_path)
    changes = characters.apply_edits(
        path, characters.EditPlan(item_repairs={"L0"}), tmp_path / "bk")
    assert any("equipped" in c for c in changes)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["GameProgress"]["Loadout"]["0"]["Durability"] == characters.REPAIR_VALUE


def test_edit_skill_xp(tmp_path):
    path = make_character(tmp_path)
    root = tmp_path / "backups"
    changes = characters.apply_edits(path, EditPlan(skill_xp={SKILL_A: 99999}), root)
    assert changes
    data = json.loads(path.read_text(encoding="utf-8"))
    skills = {s["Id"]: s["Xp"] for s in data["GameProgress"]["Skills"]["Skills"]}
    assert skills[SKILL_A] == 99999
    assert skills[SKILL_B] == 4433  # untouched


def test_edit_preserves_backup_field_and_unknowns(tmp_path):
    path = make_character(tmp_path, backup_value=53184729)
    before = json.loads(path.read_text(encoding="utf-8"))
    characters.apply_edits(path, EditPlan(heal_vitals=True), tmp_path / "b")
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["Backup"] == 53184729
    assert after["SaveCount"] == before["SaveCount"]
    assert after["meta_data"] == before["meta_data"]
    assert after["Customization"] == before["Customization"]
    assert list(after.keys()) == list(before.keys())  # field order kept


def test_edit_never_touches_the_backup_twin(tmp_path):
    path = make_character(tmp_path)
    twin = Path(str(path) + ".backup")
    twin_before = twin.read_bytes()
    characters.apply_edits(path, EditPlan(repair_all=True), tmp_path / "b")
    assert twin.read_bytes() == twin_before


def test_edit_checkpoints_first(tmp_path):
    path = make_character(tmp_path)
    root = tmp_path / "backups"
    from app.core import backups as bk
    characters.apply_edits(path, EditPlan(skill_xp={SKILL_A: 1}), root)
    cps = bk.list_checkpoints(root)
    assert len(cps) == 1
    # the checkpoint holds the PRE-edit file
    saved = json.loads((cps[0].path / path.name).read_text(encoding="utf-8"))
    skills = {s["Id"]: s["Xp"] for s in saved["GameProgress"]["Skills"]["Skills"]}
    assert skills[SKILL_A] == 5636


def test_repair_all_and_counts(tmp_path):
    path = make_character(tmp_path)
    plan = EditPlan(repair_all=True, item_counts={"8": 999})
    changes = characters.apply_edits(path, plan, tmp_path / "b")
    data = json.loads(path.read_text(encoding="utf-8"))
    inv = data["GameProgress"]["Inventory"]
    assert inv["0"]["Durability"] == characters.REPAIR_VALUE
    assert inv["8"]["Count"] == 999
    assert data["GameProgress"]["Loadout"]["0"]["Durability"] == characters.REPAIR_VALUE
    assert any("repaired" in c for c in changes)


def test_empty_plan_changes_nothing(tmp_path):
    path = make_character(tmp_path)
    before = path.read_bytes()
    assert characters.apply_edits(path, EditPlan(), tmp_path / "b") == []
    assert path.read_bytes() == before


def test_heal_values_are_clamp_friendly(tmp_path):
    path = make_character(tmp_path)
    characters.apply_edits(path, EditPlan(heal_vitals=True), tmp_path / "b")
    data = json.loads(path.read_text(encoding="utf-8"))
    char = data["GameProgress"]["Character"]
    assert char["Health"]["CurrentValue"] == characters.HEAL_VALUE
    assert char["Hydration"]["HydrationValue"] == 100.0


def test_skill_snapshot_and_diff(tmp_path):
    path = make_character(tmp_path)
    before = characters.snapshot_skills(path)
    characters.apply_edits(path, EditPlan(skill_xp={SKILL_B: 5000}), tmp_path / "b")
    after = characters.snapshot_skills(path)
    gains = characters.diff_skills(before, after)
    assert gains == [(SKILL_B, 567)]


def test_skill_labels_roundtrip(tmp_path):
    characters.save_skill_labels(tmp_path, {SKILL_A: "Chopping"})
    assert characters.load_skill_labels(tmp_path) == {SKILL_A: "Chopping"}


def test_canonical_skill_map_complete():
    """The Rosetta Stone: 11 skills, matched exactly against in-game panels."""
    assert len(characters.DEFAULT_SKILL_LABELS) == 11
    assert characters.DEFAULT_SKILL_LABELS[SKILL_A] == "Woodcutting"
    assert characters.DEFAULT_SKILL_LABELS[SKILL_B] == "Artisan"
    assert characters.DEFAULT_SKILL_LABELS["4pefO9k1lUqfA6mvHNi1SA"] == "Attack"
    assert characters.DEFAULT_SKILL_LABELS["vwY5IkQJJDwb2PKEfoc8MQ"] == "Fishing"
    assert len(set(characters.DEFAULT_SKILL_LABELS.values())) == 11  # no dupes


def test_skill_label_precedence():
    # user label wins over the canonical map
    assert characters.skill_label(SKILL_A, 0, {SKILL_A: "Trees"}) == "Trees"
    # canonical map wins over the fallback
    assert characters.skill_label(SKILL_A, 0, {}) == "Woodcutting"
    # unknown ids get a numbered fallback
    assert characters.skill_label("mystery-id", 4, {}) == "Skill 5"


def test_characters_dir_derivation(tmp_path):
    saved = tmp_path / "Saved"
    (saved / "SaveCharacters").mkdir(parents=True)
    cfg = {"local_save_dir": str(saved / "SaveGames")}
    assert characters.characters_dir(cfg) == saved / "SaveCharacters"
    cfg2 = {"characters_dir": str(tmp_path / "elsewhere")}
    assert characters.characters_dir(cfg2) == tmp_path / "elsewhere"


# -- tier swaps (upgrade / downgrade an item in place) -----------------------

def _catalog_ids() -> dict:
    from app.core import items
    return {e["name"]: i for i, e in items._catalog().items()}


def _put_item(path: Path, slot_key: str, item_id: str, **fields):
    data = json.loads(path.read_text(encoding="utf-8"))
    data["GameProgress"]["Inventory"][slot_key] = {"GUID": "keepme",
                                                   "ItemData": item_id, **fields}
    path.write_text(json.dumps(data, indent="\t"), encoding="utf-8")


def test_swap_only_plan_is_not_empty():
    assert not EditPlan(item_swaps={"0": "x"}).empty()
    assert EditPlan().empty()


def test_apply_edits_tier_swap_gear_and_ammo(tmp_path):
    from app.core import items as _items
    by = _catalog_ids()
    path = make_character(tmp_path)
    _put_item(path, "0", by["Bronze Dagger"], Durability=40)     # gear
    _put_item(path, "8", by["Bronze Arrow"], Count=5)           # ammo

    plan = EditPlan(item_swaps={"0": by["Iron Dagger"], "8": by["Iron Arrow"]},
                    item_counts={"8": 10 ** 6})                  # over-cap on purpose
    changes = characters.apply_edits(path, plan, tmp_path / "bk")
    inv = json.loads(path.read_text(encoding="utf-8"))["GameProgress"]["Inventory"]

    # gear: swapped in place, GUID kept, Count dropped, durability refreshed
    assert inv["0"]["ItemData"] == by["Iron Dagger"]
    assert inv["0"]["GUID"] == "keepme"
    assert "Count" not in inv["0"]
    assert inv["0"]["Durability"] == characters.REPAIR_VALUE
    # ammo: swapped, Durability dropped, count clamped to the NEW item's cap
    assert inv["8"]["ItemData"] == by["Iron Arrow"]
    assert "Durability" not in inv["8"]
    assert inv["8"]["Count"] == _items.max_stack(by["Iron Arrow"])
    assert changes


def test_swap_leaves_backup_field_and_twin_untouched(tmp_path):
    by = _catalog_ids()
    path = make_character(tmp_path, backup_value=424242)
    _put_item(path, "0", by["Bronze Dagger"], Durability=40)
    twin_before = (tmp_path / "Negrito.json.backup").read_text(encoding="utf-8")

    characters.apply_edits(path, EditPlan(item_swaps={"0": by["Iron Dagger"]}),
                           tmp_path / "bk")
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["Backup"] == 424242
    assert (tmp_path / "Negrito.json.backup").read_text(encoding="utf-8") == twin_before


def test_item_count_clamped_to_max_stack(tmp_path):
    from app.core import items as _items
    by = _catalog_ids()
    path = make_character(tmp_path)
    _put_item(path, "8", by["Bronze Arrow"], Count=5)
    characters.apply_edits(path, EditPlan(item_counts={"8": 10 ** 7}), tmp_path / "bk")
    inv = json.loads(path.read_text(encoding="utf-8"))["GameProgress"]["Inventory"]
    assert inv["8"]["Count"] == _items.max_stack(by["Bronze Arrow"])
