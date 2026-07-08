"""Reading — and carefully editing — Dragonwilds character files.

Characters live beside the world saves (``Saved\\SaveCharacters``) as
pretty-printed JSON with a ``.backup`` twin, mirroring the world pattern.
Verified structure (game Version 75):

- ``meta_data``: char_guid, char_name, worlds_playtime (world-guid → unix
  timestamp of last play), char_type
- ``Customization.CustomizationData``: appearance rows (BodyType, SkinTone,
  HairPreset, HairColor, FacialHairPreset, EyeColor, …)
- ``GameProgress.Character``: vitals (Health/Stamina CurrentValue,
  Sustenance/Hydration/Endurance values), Playtime_wall seconds
- ``GameProgress.Inventory``: slots with plain-integer Count / Durability
- ``GameProgress.Skills.Skills``: 11 ``{Id, Xp}`` pairs, Xp a bare integer;
  the Ids are opaque but identical across characters
- ``Backup``: unknown 32-bit value, changes every save. Tested: NOT a
  CRC32/Adler32 of any obvious content. We never touch it.

Editing philosophy: modify only the exact values asked for, leave every
other field (including ``Backup``) untouched, always checkpoint first,
always verify the result re-parses to exactly the intended structure before
replacing the file. The ``.backup`` twin is never modified — it's the game's
own second safety net and doubles as ours.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import backups
from .storage import read_json, write_json

log = logging.getLogger("dwsync.characters")

DEFAULT_CHARACTERS_DIR = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    / "RSDragonwilds" / "Saved" / "SaveCharacters"
)

# Candidate skill names for the labelling flow. The save file only has
# opaque GUIDs; players identify them (see the "identify ritual").
SKILL_NAME_CHOICES = [
    "Woodcutting", "Mining", "Firemaking", "Cooking", "Smithing",
    "Crafting", "Construction", "Runecrafting", "Melee", "Ranged",
    "Defence", "Agility", "Fishing",
]


@dataclass
class CharacterInfo:
    path: Path
    name: str = "?"
    guid: str = ""
    playtime_s: float = 0.0
    last_played: datetime | None = None
    health: float | None = None
    stamina: float | None = None
    skills: list = field(default_factory=list)       # [{"Id","Xp"}]
    total_xp: int = 0
    inventory_slots: int = 0
    appearance: dict = field(default_factory=dict)   # {slot: rowName}
    save_count: int = 0


def characters_dir(cfg: dict) -> Path:
    """Configured folder, else derived from the save folder, else default."""
    configured = (cfg or {}).get("characters_dir")
    if configured:
        return Path(configured)
    save_dir = (cfg or {}).get("local_save_dir")
    if save_dir:
        sibling = Path(save_dir).parent / "SaveCharacters"
        if sibling.exists():
            return sibling
    return DEFAULT_CHARACTERS_DIR


def character_files(folder) -> list[Path]:
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted(p for p in folder.glob("*.json") if p.is_file())


def _appearance_rows(data: dict) -> dict:
    rows = {}
    custom = (data.get("Customization") or {}).get("CustomizationData") or {}
    for slot, entry in custom.items():
        if isinstance(entry, dict) and entry.get("rowName"):
            rows[slot] = entry["rowName"]
    return rows


def parse_character(path) -> CharacterInfo | None:
    path = Path(path)
    data = read_json(path)
    if not isinstance(data, dict):
        return None
    info = CharacterInfo(path=path)
    meta = data.get("meta_data") or {}
    info.name = meta.get("char_name") or path.stem
    info.guid = meta.get("char_guid", "")
    info.save_count = data.get("SaveCount", 0)

    stamps = [v for v in (meta.get("worlds_playtime") or {}).values()
              if isinstance(v, (int, float)) and v > 1_000_000_000]
    if stamps:
        try:
            info.last_played = datetime.fromtimestamp(max(stamps), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            pass

    progress = data.get("GameProgress") or {}
    char = progress.get("Character") or {}
    info.playtime_s = float(char.get("Playtime_wall") or 0.0)
    health = char.get("Health") or {}
    stamina = char.get("Stamina") or {}
    info.health = health.get("CurrentValue")
    info.stamina = stamina.get("CurrentValue")

    skills = ((progress.get("Skills") or {}).get("Skills")) or []
    info.skills = [s for s in skills if isinstance(s, dict) and "Id" in s]
    info.total_xp = sum(int(s.get("Xp") or 0) for s in info.skills)

    inventory = progress.get("Inventory") or {}
    info.inventory_slots = sum(1 for k, v in inventory.items()
                               if isinstance(v, dict) and k != "MaxSlotIndex")
    info.appearance = _appearance_rows(data)
    return info


def list_characters(folder) -> list[CharacterInfo]:
    infos = []
    for p in character_files(folder):
        info = parse_character(p)
        if info:
            infos.append(info)
    infos.sort(key=lambda i: i.last_played or datetime.min.replace(tzinfo=timezone.utc),
               reverse=True)
    return infos


def portrait_descriptor(info: CharacterInfo) -> str:
    """Compact appearance string safe to embed in the shared manifest."""
    rows = info.appearance
    parts = [
        rows.get("BodyType", ""), rows.get("SkinTone", ""),
        rows.get("HairPreset", ""), rows.get("HairColor", ""),
        rows.get("FacialHairPreset", ""), rows.get("EyeColor", ""),
    ]
    return "|".join(p[:24] for p in parts)


# ---------------------------------------------------------------------------
# editing — The Dragon's Bargain
# ---------------------------------------------------------------------------

@dataclass
class EditPlan:
    """What the grimoire wants changed. Only these values are touched."""
    skill_xp: dict = field(default_factory=dict)       # skill Id -> new Xp int
    heal_vitals: bool = False                          # health/stamina to max-ish
    repair_all: bool = False                           # every Durability -> max seen
    item_counts: dict = field(default_factory=dict)    # slot key -> new Count int

    def empty(self) -> bool:
        return not (self.skill_xp or self.heal_vitals or self.repair_all
                    or self.item_counts)


REPAIR_VALUE = 9999
HEAL_VALUE = 100000.0   # game clamps to the character's real maximum on load


def apply_edits(path, plan: EditPlan, backup_root) -> list[str]:
    """Apply an EditPlan to a character file. Returns a list of change notes.

    Safety: checkpoint first; modify only planned values in the parsed dict;
    re-serialize; verify the result parses back to the modified dict; atomic
    replace. The .backup twin and the Backup field are never touched.
    """
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    changes: list[str] = []

    # 1. checkpoint the character (both json and its .backup twin)
    stamp = datetime.now().strftime("%H:%M")
    backups.create_checkpoint(path.parent, path.stem,
                              f"Before the bargain ({stamp})", backup_root)

    progress = data.get("GameProgress") or {}

    if plan.skill_xp:
        skills = ((progress.get("Skills") or {}).get("Skills")) or []
        by_id = {s.get("Id"): s for s in skills if isinstance(s, dict)}
        for skill_id, new_xp in plan.skill_xp.items():
            entry = by_id.get(skill_id)
            if entry is None:
                continue
            old = entry.get("Xp")
            new_xp = max(0, int(new_xp))
            if old != new_xp:
                entry["Xp"] = new_xp
                changes.append(f"skill {skill_id[:8]}…: {old} → {new_xp} xp")

    if plan.heal_vitals:
        char = progress.get("Character") or {}
        for key in ("Health", "Stamina"):
            vital = char.get(key)
            if isinstance(vital, dict) and "CurrentValue" in vital:
                vital["CurrentValue"] = HEAL_VALUE
        for key, sub in (("Sustenance", "SustenanceValue"),
                         ("Hydration", "HydrationValue"),
                         ("Endurance", "EnduranceValue")):
            vital = char.get(key)
            if isinstance(vital, dict) and sub in vital:
                vital[sub] = 100.0
        changes.append("vitals restored")

    inventory = progress.get("Inventory") or {}
    if plan.repair_all:
        repaired = 0
        for key, slot in inventory.items():
            if isinstance(slot, dict) and "Durability" in slot:
                slot["Durability"] = REPAIR_VALUE
                repaired += 1
        loadout = progress.get("Loadout") or {}
        for key, slot in loadout.items():
            if isinstance(slot, dict) and "Durability" in slot:
                slot["Durability"] = REPAIR_VALUE
                repaired += 1
        if repaired:
            changes.append(f"{repaired} items repaired")

    for slot_key, new_count in (plan.item_counts or {}).items():
        slot = inventory.get(str(slot_key))
        if isinstance(slot, dict) and "Count" in slot:
            old = slot.get("Count")
            new_count = max(1, int(new_count))
            if old != new_count:
                slot["Count"] = new_count
                changes.append(f"slot {slot_key}: count {old} → {new_count}")

    if not changes:
        return []

    # 2. serialize like the game does (tabs, unescaped unicode) and verify
    new_text = json.dumps(data, indent="\t", ensure_ascii=False)
    if json.loads(new_text) != data:  # paranoia: round-trip must be exact
        raise ValueError("round-trip verification failed; file left untouched")

    # 3. atomic replace
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    os.replace(tmp, path)
    log.info("Dragon's bargain applied to %s: %s", path.name, "; ".join(changes))
    return changes


# ---------------------------------------------------------------------------
# skill labelling — the identify ritual
# ---------------------------------------------------------------------------

def load_skill_labels(app_dir) -> dict:
    return read_json(Path(app_dir) / "skill_labels.json", {}) or {}


def save_skill_labels(app_dir, labels: dict):
    write_json(Path(app_dir) / "skill_labels.json", labels)


def snapshot_skills(path) -> dict:
    """{skill Id -> Xp} right now, for diffing after a play session."""
    info = parse_character(path)
    return {s["Id"]: int(s.get("Xp") or 0) for s in (info.skills if info else [])}


def diff_skills(before: dict, after: dict) -> list[tuple[str, int]]:
    """Skills that gained XP, biggest gain first."""
    gains = []
    for skill_id, xp in after.items():
        gained = xp - before.get(skill_id, 0)
        if gained > 0:
            gains.append((skill_id, gained))
    gains.sort(key=lambda t: -t[1])
    return gains
