"""Game profiles: everything WorldSync needs to know about one game.

A profile is plain data. It says where the game keeps its saves, how to tell
one world apart from another inside that folder, which files make up a
world, and how to launch and watch the game. The sync core never sees a
profile directly - ``config.effective_cfg`` flattens the bits it needs
(save folder, file patterns, mirror flag) into the same dict it has always
taken, so adding a game never touches the protocol.

Path templates use a few tokens (``{LOCALAPPDATA}``, ``{APPDATA}``,
``{LOCALLOW}``, ``{SAVEDGAMES}``, ``{USERPROFILE}``, ``{DOCUMENTS}``) and may
contain ``*`` segments for folders named after a Steam ID. When a ``*``
matches several folders, the most recently written one wins - that is the
account that played last.

File patterns are globs relative to the save folder. ``{world}`` is the
world id and ``{map}`` is the part before the first ``/`` (7 Days to Die
keeps a world as ``<map>/<save>``). ``patterns=None`` means the original
Dragonwilds rule: every file in the folder whose name starts with the world
name. That keeps existing Dragonwilds groups byte-for-byte compatible.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

VERIFIED = "verified"   # tested end to end with real saves
BETA = "beta"           # layout from community guides; waiting on reports


@dataclass(frozen=True)
class Discover:
    """How to list the worlds that already exist in a save folder."""
    glob: str                 # relative to the save folder
    regex: str                # applied to the match's path relative to the folder
    dirs: bool = False        # match folders instead of files


@dataclass(frozen=True)
class GameProfile:
    id: str
    name: str
    steam_app_id: str
    process_names: tuple[str, ...]
    save_roots: tuple[str, ...]           # templates, first that exists wins
    discover: tuple[Discover, ...]
    patterns: tuple[str, ...] | None      # None = legacy prefix rule
    mirror: bool = False                  # delete files the other side no longer has
    status: str = BETA
    tagline: str = ""                     # one line for the library card
    world_word: str = "world"             # what the game calls it: world, save, slot
    world_hint: str = ""                  # how to recognise the right world
    caveats: tuple[str, ...] = ()         # shown before the first share
    label_fmt: str = ""                   # e.g. "Slot {slot}" for numbered worlds
    label_json: tuple[str, str] | None = None  # (file inside the world, key) for a nicer name
    extras: tuple[str, ...] = field(default=())  # optional feature flags, e.g. "characters"
    short_name: str = ""                  # for tight spots; defaults to name

    @property
    def verified(self) -> bool:
        return self.status == VERIFIED

    @property
    def short(self) -> str:
        return self.short_name or self.name


# -- the library ----------------------------------------------------------------

DRAGONWILDS = GameProfile(
    id="dragonwilds",
    name="RuneScape: Dragonwilds",
    steam_app_id="1374490",
    process_names=("RSDragonwilds.exe",),
    save_roots=("{LOCALAPPDATA}/RSDragonwilds/Saved/SaveGames",),
    discover=(Discover("*.sav", r"^(?P<w>.+)\.sav$"),),
    patterns=None,
    status=VERIFIED,
    tagline="Dark fantasy survival in Ashenfall",
    world_hint="The world name as it appears in the game's world list.",
    extras=("characters", "secret", "rich_presence"),
    short_name="Dragonwilds",
)

VALHEIM = GameProfile(
    id="valheim",
    name="Valheim",
    steam_app_id="892970",
    process_names=("valheim.exe",),
    save_roots=("{LOCALLOW}/IronGate/Valheim/worlds_local",),
    discover=(Discover("*.fwl", r"^(?P<w>[^/]+)\.fwl$"),
              Discover("*", r"^(?P<w>[^/.]+)$", dirs=True)),
    patterns=("{world}.fwl*", "{world}.db*", "{world}/**/*"),
    mirror=True,
    tagline="Viking afterlife, ten worlds deep",
    world_hint="The world name from the Start Game screen.",
    caveats=(
        "Worlds stored in Steam Cloud aren't in this folder. In Valheim, "
        "select the world, choose Manage Saves and Move to Local first.",
        "Characters live on each player's own PC, so everyone keeps their own "
        "Viking - only the world travels.",
    ),
)

ENSHROUDED = GameProfile(
    id="enshrouded",
    name="Enshrouded",
    steam_app_id="1203620",
    process_names=("enshrouded.exe",),
    save_roots=("{SAVEDGAMES}/Enshrouded",
                "{PROGRAMFILESX86}/Steam/userdata/*/1203620/remote"),
    discover=(Discover("*", r"^(?P<w>[0-9a-f]{8})$"),),
    patterns=("{world}", "{world}-*", "{world}_*"),
    mirror=True,
    tagline="Fight back the Shroud together",
    world_hint="Enshrouded names world files with an 8 character code. "
               "Pick the one you played most recently.",
    caveats=(
        "With Steam Cloud saves on, Enshrouded keeps worlds under Steam\\userdata. "
        "WorldSync looks there as well; browse to it if nothing shows up.",
    ),
)

PALWORLD = GameProfile(
    id="palworld",
    name="Palworld",
    steam_app_id="1623730",
    process_names=("Palworld-Win64-Shipping.exe", "Palworld.exe"),
    save_roots=("{LOCALAPPDATA}/Pal/Saved/SaveGames/*",),
    discover=(Discover("*", r"^(?P<w>[0-9A-Fa-f]{32})$", dirs=True),),
    patterns=("{world}/**/*",),
    mirror=True,
    tagline="Catch, build, and survive with Pals",
    world_word="world",
    world_hint="Palworld names world folders with a long code. "
               "Pick the one you played most recently.",
    caveats=(
        "Palworld ties the host's character to the host's PC. When a "
        "different friend hosts, the original host's character can look "
        "reset. Everyone else keeps theirs. Community tools such as "
        "PalworldSaveTools can move a host character if you need it.",
    ),
)

CORE_KEEPER = GameProfile(
    id="core_keeper",
    name="Core Keeper",
    steam_app_id="1621690",
    process_names=("CoreKeeper.exe",),
    save_roots=("{LOCALLOW}/Pugstorm/Core Keeper/Steam/*",),
    discover=(Discover("worlds/*.world.gzip", r"^worlds/(?P<w>\d+)\.world\.gzip$"),),
    patterns=("worlds/{world}.world.gzip*", "maps/*/{world}.mapparts.gzip*",
              "worldinfos/{world}.*", "worldgenparams/{world}.*"),
    mirror=True,
    tagline="Mine deep, wake the Core",
    world_word="slot",
    world_hint="Core Keeper numbers worlds by their slot on the world menu.",
    label_fmt="Slot {slot}",
    caveats=(
        "Core Keeper stores worlds by slot number, so everyone in the group "
        "uses the same slot for this world. If a friend already has a "
        "different world in that slot, WorldSync backs it up before replacing it.",
    ),
)

SONS_OF_THE_FOREST = GameProfile(
    id="sons_of_the_forest",
    name="Sons of the Forest",
    steam_app_id="1326470",
    process_names=("SonsOfTheForest.exe",),
    save_roots=("{LOCALLOW}/Endnight/SonsOfTheForest/Saves/*/Multiplayer",),
    discover=(Discover("*", r"^(?P<w>\d+)$", dirs=True),),
    patterns=("{world}/**/*",),
    mirror=True,
    tagline="Survive the island, together",
    world_word="save",
    world_hint="Multiplayer saves are numbered folders. Pick the one you "
               "played most recently.",
    caveats=(
        "The host's inventory and stats are stored inside the save. Whoever "
        "hosts the shared save carries that host inventory; guests keep their "
        "own from the MultiplayerClient folder.",
    ),
)

V_RISING = GameProfile(
    id="v_rising",
    name="V Rising",
    steam_app_id="1604030",
    process_names=("VRising.exe",),
    save_roots=("{LOCALLOW}/Stunlock Studios/VRising/Saves/v*",),
    discover=(Discover("*", r"^(?P<w>[^/]+)$", dirs=True),),
    patterns=("{world}/**/*",),
    mirror=True,
    tagline="Rise from the grave, build a castle",
    world_hint="Each private game is a folder with a long code name.",
    label_json=("ServerHostSettings.json", "Name"),
    caveats=(
        "Vampires are stored per Steam account inside the world, so every "
        "friend keeps their own character whoever hosts.",
    ),
)

GROUNDED = GameProfile(
    id="grounded",
    name="Grounded",
    steam_app_id="962130",
    process_names=("Maine-Win64-Shipping.exe", "Grounded.exe"),
    save_roots=("{SAVEDGAMES}/Grounded/[0-9]*", "{SAVEDGAMES}/Grounded"),
    discover=(Discover("*", r"^(?P<w>[^/.]+)$", dirs=True),),
    patterns=("{world}/**/*",),
    mirror=True,
    tagline="Shrunk to the size of an ant",
    world_hint="Each world is a folder with a screenshot inside to recognise it.",
    caveats=(
        "Grounded on Game Pass keeps saves in a protected folder WorldSync "
        "can't reach. The Steam version works.",
    ),
)

RAFT = GameProfile(
    id="raft",
    name="Raft",
    steam_app_id="648800",
    process_names=("Raft.exe",),
    save_roots=("{LOCALLOW}/Redbeet Interactive/Raft/User/User_*/World",),
    discover=(Discover("*", r"^(?P<w>[^/]+)$", dirs=True),),
    patterns=("{world}/**/*",),
    mirror=True,
    tagline="Adrift with a hook and a shark",
    world_hint="The world name from Load World.",
)

SEVEN_DAYS = GameProfile(
    id="seven_days_to_die",
    name="7 Days to Die",
    steam_app_id="251570",
    process_names=("7DaysToDie.exe",),
    save_roots=("{APPDATA}/7DaysToDie",),
    discover=(Discover("Saves/*/*", r"^Saves/(?P<w>[^/]+/[^/]+)$", dirs=True),),
    patterns=("Saves/{world}/**/*", "GeneratedWorlds/{map}/**/*"),
    mirror=True,
    tagline="Survive the blood moon horde",
    world_word="save",
    world_hint="Your save names from Continue Game; the map travels along with it.",
    label_fmt="{save}",
    caveats=(
        "A random-gen map travels with the save the first time, so the "
        "first share can be a few hundred MB. After that only changes move.",
    ),
)

ALL: tuple[GameProfile, ...] = (
    DRAGONWILDS, VALHEIM, ENSHROUDED, PALWORLD, CORE_KEEPER,
    SONS_OF_THE_FOREST, V_RISING, GROUNDED, RAFT, SEVEN_DAYS,
)
BY_ID = {g.id: g for g in ALL}
DEFAULT_GAME = DRAGONWILDS.id


def get(game_id: str | None) -> GameProfile:
    """Profile by id; unknown ids fall back to Dragonwilds (the v1 game)."""
    return BY_ID.get(game_id or DEFAULT_GAME, DRAGONWILDS)


# -- path resolution --------------------------------------------------------------

def _tokens() -> dict[str, str]:
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    return {
        "USERPROFILE": str(home),
        "LOCALAPPDATA": os.environ.get("LOCALAPPDATA") or str(home / "AppData" / "Local"),
        "APPDATA": os.environ.get("APPDATA") or str(home / "AppData" / "Roaming"),
        "LOCALLOW": str(home / "AppData" / "LocalLow"),
        "SAVEDGAMES": str(home / "Saved Games"),
        "DOCUMENTS": str(home / "Documents"),
        "PROGRAMFILESX86": os.environ.get("ProgramFiles(x86)") or "C:/Program Files (x86)",
    }


def _newest(paths: list[Path]) -> Path | None:
    best, best_t = None, -1.0
    for p in paths:
        try:
            t = p.stat().st_mtime
        except OSError:
            continue
        if t > best_t:
            best, best_t = p, t
    return best


def expand(template: str, tokens: dict[str, str] | None = None) -> Path | None:
    """Turn a template into a real folder, or None if it doesn't exist here."""
    text = template.format(**(tokens or _tokens()))
    parts = Path(text).parts
    current = Path(parts[0])
    for part in parts[1:]:
        if "*" in part or "?" in part:
            try:
                matches = [p for p in current.glob(part) if p.is_dir()]
            except OSError:
                return None
            current = _newest(matches)
            if current is None:
                return None
        else:
            current = current / part
    try:
        return current if current.is_dir() else None
    except OSError:
        return None


def default_save_dir(profile: GameProfile, tokens: dict[str, str] | None = None) -> Path | None:
    for template in profile.save_roots:
        found = expand(template, tokens)
        if found:
            return found
    return None


def fallback_save_dir(profile: GameProfile) -> Path:
    """Where the save folder normally is, for display when it doesn't exist yet."""
    text = profile.save_roots[0].format(**_tokens())
    # stop at the first wildcard: that part is per-account
    keep = []
    for part in Path(text).parts:
        if "*" in part or "?" in part:
            break
        keep.append(part)
    return Path(*keep)


# -- world discovery ----------------------------------------------------------------

@dataclass
class FoundWorld:
    id: str
    label: str
    modified: datetime | None
    size: int


def _tree_size_and_mtime(path: Path) -> tuple[int, float]:
    if path.is_file():
        st = path.stat()
        return st.st_size, st.st_mtime
    size, newest = 0, path.stat().st_mtime
    for f in path.rglob("*"):
        try:
            if f.is_file():
                st = f.stat()
                size += st.st_size
                newest = max(newest, st.st_mtime)
        except OSError:
            continue
    return size, newest


def _label(profile: GameProfile, world_id: str, root: Path) -> str:
    if profile.label_json:
        rel, key = profile.label_json
        try:
            import json
            data = json.loads((root / world_id / rel).read_text(encoding="utf-8-sig"))
            name = str(data.get(key) or "").strip()
            if name:
                return name
        except (OSError, ValueError, AttributeError):
            pass
    if profile.label_fmt:
        slot = int(world_id) + 1 if world_id.isdigit() else world_id
        first, _, last = world_id.partition("/")
        return profile.label_fmt.format(world=world_id, slot=slot, map=first,
                                        save=last or first)
    return world_id.replace("/", " / ")


def discover_worlds(profile: GameProfile, save_dir) -> list[FoundWorld]:
    """Worlds that exist in `save_dir`, most recently played first."""
    root = Path(save_dir)
    if not root.is_dir():
        return []
    found: dict[str, FoundWorld] = {}
    for spec in profile.discover:
        rx = re.compile(spec.regex)
        try:
            candidates = list(root.glob(spec.glob))
        except OSError:
            continue
        for path in candidates:
            try:
                if spec.dirs != path.is_dir():
                    continue
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            m = rx.match(rel)
            if not m:
                continue
            wid = m.group("w")
            try:
                size, mtime = _tree_size_and_mtime(path)
            except OSError:
                size, mtime = 0, 0.0
            prev = found.get(wid)
            when = datetime.fromtimestamp(mtime) if mtime else None
            if prev:
                prev.size += size
                if when and (not prev.modified or when > prev.modified):
                    prev.modified = when
            else:
                found[wid] = FoundWorld(wid, _label(profile, wid, root), when, size)
    return sorted(found.values(),
                  key=lambda w: w.modified or datetime.min, reverse=True)


def is_valid_world_id(world_id: str) -> bool:
    """Reject ids that could escape the save folder when used in a pattern."""
    if not world_id or world_id.strip() != world_id:
        return False
    parts = world_id.replace("\\", "/").split("/")
    return all(p and p not in (".", "..") for p in parts) and ":" not in world_id


# -- setup guides ------------------------------------------------------------------
# Shown in the app's per-game setup guide and in docs/GAMES.md. Written for the
# person setting it up the first time: what to do in the game before WorldSync
# can see the world, and what to tell the group.

SETUP_STEPS: dict[str, tuple[str, ...]] = {
    "dragonwilds": (
        "Start Dragonwilds, create or load the world you want to share, then quit to desktop.",
        "In WorldSync, pick that world by its name from the in-game world list.",
        "Characters are yours: everyone keeps their own character file, only the world travels. "
        "Turn on Character travel (world menu → Characters) to take yours between your own PCs.",
    ),
    "valheim": (
        "Start Valheim, choose Start Game and select your world.",
        "If the world is stored in Steam Cloud, use Manage Saves and Move to Local first, "
        "otherwise WorldSync can't see it.",
        "Quit to desktop, then pick the world by its name in WorldSync.",
        "Characters stay on each player's PC, so everyone brings their own Viking.",
        "Playing with mods? Everyone needs the same mods, the same as joining a normal server.",
    ),
    "enshrouded": (
        "Start Enshrouded, load the world you want to share once, then quit to desktop.",
        "Enshrouded names worlds with an 8 character code. WorldSync lists them with the most "
        "recently played first, so the top one is usually the right one.",
        "With Steam Cloud saves on, the worlds live under Steam\\userdata. WorldSync looks "
        "there too; if it still finds nothing, browse to Steam\\userdata\\<number>\\1203620\\remote.",
        "Characters are separate files, so every player keeps their own.",
    ),
    "palworld": (
        "The person who created the co-op world starts Palworld, loads it, then quits to desktop.",
        "Worlds are folders with a long code name. WorldSync lists them with the most recently "
        "played first.",
        "Know the host quirk: Palworld ties the original host's character to their PC. When a "
        "friend hosts the shared world, the original host's character can look reset. Everyone "
        "else keeps theirs. PalworldSaveTools can move a host character if you need it.",
        "This is for the in-game co-op world, not a dedicated server.",
    ),
    "core_keeper": (
        "Start Core Keeper, load the world, then quit to desktop.",
        "Worlds are numbered by their slot on the world menu (slot 1 is file 0). Pick the slot "
        "you play in.",
        "Everyone in the group uses that same slot for this world. If a friend already has a "
        "different world there, WorldSync backs it up before replacing it, but a free slot is "
        "cleaner.",
        "Characters are separate, so everyone keeps their own.",
    ),
    "sons_of_the_forest": (
        "The host starts a Multiplayer game, saves at a shelter or tent, then quits to desktop.",
        "Multiplayer saves are numbered folders. WorldSync lists them with the most recently "
        "played first.",
        "The host's own inventory and stats live inside the save, so whoever hosts the shared "
        "world plays with that host inventory. Guests keep theirs.",
    ),
    "v_rising": (
        "Start V Rising and host a Private Game, play a moment so it saves, then quit to desktop.",
        "WorldSync shows the world by the server name you gave it.",
        "Every vampire is stored per Steam account inside the world, so all friends keep their "
        "own character whoever hosts. The game settings travel with the world too.",
    ),
    "grounded": (
        "Use the Steam version. Game Pass saves sit in a protected folder WorldSync can't reach.",
        "Start Grounded, load the world, then quit to desktop.",
        "Each world is its own folder. WorldSync lists them with the most recently played first.",
    ),
    "raft": (
        "Start Raft, load the world you want to share, then quit to desktop.",
        "Not sure which folder it is? Load World in Raft has an Open Save Folder button.",
        "Pick the world by its name in WorldSync.",
    ),
    "seven_days_to_die": (
        "Start 7 Days to Die, continue the save you want to share, then quit to desktop.",
        "Pick the save by its name. For a random-gen map, the generated map folder travels "
        "with it automatically.",
        "The first share can be a few hundred MB. Let your cloud drive finish uploading before "
        "a friend presses Play.",
        "Everyone needs the same game version (the same Steam beta branch, if you use one).",
    ),
}

# Shown for every game, after the game's own steps.
COMMON_STEPS: tuple[str, ...] = (
    "Everyone in the group needs the game, a cloud drive app (Google Drive, Dropbox or "
    "OneDrive) and WorldSync.",
    "Always start the game with Play in WorldSync. It pulls the newest world first and shares "
    "yours back when you close the game.",
    "One person hosts at a time. Playing together still works the normal way: one person "
    "hosts in-game and the others join; WorldSync makes sure that host has the latest world.",
)

_HUMAN_TOKENS = {
    "{LOCALAPPDATA}": "%LOCALAPPDATA%",
    "{APPDATA}": "%APPDATA%",
    "{LOCALLOW}": "%USERPROFILE%\\AppData\\LocalLow",
    "{SAVEDGAMES}": "%USERPROFILE%\\Saved Games",
    "{USERPROFILE}": "%USERPROFILE%",
    "{DOCUMENTS}": "%USERPROFILE%\\Documents",
    "{PROGRAMFILESX86}": "C:\\Program Files (x86)",
}


def setup_steps(profile: GameProfile) -> tuple[str, ...]:
    return SETUP_STEPS.get(profile.id, ())


def human_save_path(template: str) -> str:
    """'{LOCALLOW}/Pal/*' -> '%USERPROFILE%\\AppData\\LocalLow\\Pal\\<account>'."""
    text = template
    for token, human in _HUMAN_TOKENS.items():
        text = text.replace(token, human)
    parts = []
    for part in text.split("/"):
        if part in ("*", "[0-9]*"):
            part = "<account number>"
        elif part == "v*":          # V Rising's save-format folder
            part = "v3"
        elif "*" in part:
            part = part.replace("*", "<number>")
        parts.append(part)
    return "\\".join(parts)
