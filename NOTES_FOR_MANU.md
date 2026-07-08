# Notes for Manu

## v1.3.1 — the Rosetta Stone

You cracked the skill names yourself by screenshotting the in-game panels —
all 11 XP values matched the file **exactly and uniquely** (verified against
your freshly-saved file, twice). The canonical map is now baked into the app,
so **everyone's grimoire shows real skill names out of the box**:

| Skill | GUID |
|---|---|
| Attack | `4pefO9k1lUqfA6mvHNi1SA` |
| Magic | `0hreSMRVXUihq9qjDO2CFA` |
| Ranged | `heq7u88Q2UuLXFqLGTVwQw` |
| Mining | `jqX0Gh6QI0GFFPCDFK_CJQ` |
| Woodcutting | `4zYUGF5u_0KbMLkWJmmBbQ` |
| Artisan | `Wf3i7Ha-B06DH719j1vtBw` |
| Construction | `waK-8EyQFQ2xEjCGYmuTRQ` |
| Cooking | `Tn7t6DQyX0-Q0cM5K7B90A` |
| Farming | `PyUi-0LU_riFY46AnnFiWg` |
| Runecrafting | `NOqC-z-2ckqi0El22qMFlw` |
| Fishing | `vwY5IkQJJDwb2PKEfoc8MQ` |

Grimoire got easy mode: skills alphabetized under their real names, with
**+1k / +10k** chips per skill (they stack on the current or typed value).
The identify ritual stays as future-proofing for skills a game update adds.
Note: the panels show XP *thresholds* per level (e.g. 6,439/6,608), but the
level curve isn't fully derivable from these data points, so the grimoire
deals in XP, not levels — type what the panel shows for the level you want.

## v1.3 — characters, the Secret, and the saga

**Everything you greenlit shipped**, in `dist\DragonwildsSync.exe` (v1.3.0,
44.8 MB, launches clean). **112 tests** (was 87). Sync core still frozen —
character travel literally reuses it unchanged, which is why it inherits
every conflict guarantee.

### What I found before building (the grounding)
- Characters live in `Saved\SaveCharacters\` as **plain JSON** with `.backup`
  twins — not the scary binary I'd feared. Name, playtime, appearance,
  vitals, inventory (plain-int counts/durability), and 11 skills as
  `{Id, Xp}` with **bare-integer XP** and Ids identical across characters.
- The `Backup` field changes every save; I tested CRC32/Adler32 over every
  plausible byte range — **no match**, so it's not a simple content checksum.
  The editor never touches it. **First bargain on a real character is a
  supervised experiment**: checkpoint is automatic, and if the game rejects
  the file, restore from Characters → Backups costs ten seconds. Please try
  one small edit (e.g. +1 xp) before telling the group about the secret.
- One of your characters is named with invisible RTL Unicode marks
  (`1⁧⁧Minblyat`) — handled, and honestly, respect.

### The Secret (don't read this aloud in the group chat)
Click the **dragon eye in the titlebar five times, quickly**. It stays
unlocked afterwards (bottom of the world menu: *The Dragon's Bargain*).
Skill XP rewrites, restore-vitals, repair-everything. Skill names are
opaque GUIDs in the file, so the grimoire ships with an **identify ritual**:
begin it, train exactly one skill in game, finish it, and name what you
trained — the label sticks forever. Every bargain: game-closed check →
auto-checkpoint → only the asked-for numbers change → the game's own
`.backup` twin stays untouched as a second net.

### Judgment calls (v1.3)
1. **Character travel is per-player and opt-in** (Characters page toggle) —
   your character follows *you* across *your* PCs via
   `shared/characters/<you>/`. It never touches friends' characters.
2. **Portraits are stylised guesses**: the save stores swatch names
   (SkinTone8, Color6), not RGB. I mapped them to consistent palettes — a
   character always looks the same everywhere, even if not game-exact.
3. **Vitals "heal" writes a huge CurrentValue** on the theory the game
   clamps to max on load — part of the same first-bargain experiment.
4. **Group history keeps 3 versions ≈ 9 MB** of cloud space per world.
5. **Discord Rich Presence needs a free app id** (discord.com/developers →
   New Application → copy the ID into Settings). Without it, the feature
   silently stays off. No dependency was added — the IPC pipe is hand-rolled.
6. **Saga totals**: all-time via `stats.json` starting *now*; sessions from
   before v1.3 only exist in the capped manifest history, so the first days
   may undercount old sessions. It says so on the page ("totals cover…").

---

## v1.2 — the redesign + "everything a friend group could want" pass

**Built on your feedback: the UI looked AI-made, and you wanted more features.**
Both addressed. `dist\DragonwildsSync.exe` is now **v1.2.0** (44.7 MB, launches
clean, bundled fonts confirmed loading inside the package). **87 tests green**
(was 57). Sync core still frozen — untouched except the two additive helpers
from v1.1. Git history is incremental across the whole session.

### The new look (Game-launcher × Arcane grimoire, as you asked)
- Every world gets a **procedurally-painted hero banner** — a moonlit,
  ember-flecked landscape seeded from the world's name and tinted by its own
  colour, so each world looks distinct. No image files shipped; it's all
  painted (`app/ui/banner.py`).
- World name in **Cinzel Decorative**, headings/wordmark in **Cinzel**, session
  notes in **EB Garamond** italic (all SIL OFL, bundled in the exe). Ember-gold
  accent now rides alongside the emerald. **PLAY** breathes at rest and flares
  on hover.
- Onboarding welcome + About restyled to match. See `docs/screenshots/` —
  re-rendered, 20 states.

### New features (you said "all of them, and more")
Tier-1 asks, all shipped:
- **Auto-update through the shared folder.** You (host) hit Settings → *Publish
  this version to friends*; it copies the running exe into the folder's `_app`
  dir with a version manifest. Everyone else gets an **Update bar** and swaps
  in place on click. Self-swap uses a wait-then-replace batch script (Windows
  won't overwrite a running exe). Only works from the packaged exe, not source.
- **"Test my setup"** (Settings) — checklist: save folder, world save, shared
  folder writable, cloud drive, sync state, game launch.
- **Save safety** — a corrupt/zero-byte or still-downloading save is never
  shared or pulled over. This lives in the controller *around* the frozen sync
  core, so it can't affect protocol correctness.
- **Pass the turn** — pick a friend, they get a tray ping ("it's your turn").

More, added on top:
- **Named checkpoints** + delete, beside the auto-backups (Backups page).
- **Phone status page** — optional `status.html` in the shared folder (toggle
  in Settings), checkable from a phone's Drive app. Zero backend.
- **Richer conflict prompt** — now shows both saves' sizes and save-times.

### Judgment calls worth a glance
1. **Auto-update trust model:** anyone who can write the shared folder can
   publish an update that others will run. That's the same trust you already
   extend to everyone in a shared-save group, but worth knowing. If you want,
   I can add a "only accept updates published by <you>" pin — say the word.
2. **Update self-swap** is the standard Windows trick (stage + batch script
   that waits for exit, copies, relaunches). It's the one bit that can't be
   unit-tested end-to-end; I tested the pieces (version compare, publish/detect,
   script generation) and the app launch, but **please do one real update
   dry-run** between two machines before relying on it with friends.
3. **Fonts add ~1 MB** and are bundled + confirmed loading in the packaged exe.
4. **Save-safety gate skips the push** on a bad file rather than asking — the
   safe default is "don't poison the group; keep the last good save."
5. Status page is **off unless the toggle is on**? No — it defaults **on**
   (`publish_status_page: true`). It only writes a small HTML file; flip it off
   in Settings if you'd rather not.

### Deferred (still), and honestly why
- **Real .sav parsing** for in-game stats — still a rainy-day spike, same risks
  as before (undocumented binary, breaks on game updates, must never write).
- **World branching** — design sketch remains in the Tier C notes below.
- **Discord Rich Presence** — needs a discord IPC dependency; the webhook
  already covers "notify the group," so I left it out to avoid the dependency.
- **Launch sound / animations** — would need QtMultimedia; skipped to keep the
  exe lean. The PLAY breathing glow scratches some of that itch.

---

# Notes for Manu — overnight build, 2026-07-08 → 09

## Morning summary

**v1.1.0 is built, tested, and sitting in `dist\DragonwildsSync.exe`
(44 MB).** 52 tests green (was 15). Your real config was migrated to the new
multi-world format on this machine tonight (during smoke testing — same
migration your friends' apps will do); the originals are safe at
`%APPDATA%\DragonwildsSync\config.v1.bak` / `state.v1.bak`. Git history is
clean and incremental — `git log --oneline` reads as the story of the night.

### To send a fresh invite to your friends (your morning checklist)

1. Give them the new `dist\DragonwildsSync.exe` (drop it in
   `G:\My Drive\Dragonwilds Sync` itself — easiest) and have everyone
   replace their old copy. Old and new apps sync together fine, but only
   the new one has invites/presence/tray.
2. Open the app → **Invite friends** (top right).
3. One-time: share the folder in the Drive UI — the page walks you through
   it (right-click folder → Share → *Anyone with the link* → Copy link),
   paste the link.
4. **Generate invite code** → **Copy code** → paste into the group chat.
5. A friend picks **“Join with an invite code”** during their setup. Their
   one manual click is Google's *“Add shortcut to Drive”* — the app does
   the rest, including finding the synced folder automatically.

### What shipped, by tier

**Tier 0 — all of it**
- Invite codes: generated/decoded 100% locally (`DWS1.` + zlib + base64url;
  ~200 chars — "short" within the limits of carrying a full Drive URL).
- Onboarding forks into **Create a new world** / **Join with an invite
  code**; join opens the share link in the browser and watches every cloud
  root on the machine until the folder syncs in, then autofills everything.
  (The watcher literally validated itself against your real
  `G:\My Drive\Dragonwilds Sync` during screenshot testing — found it
  first tick.)
- Google-Drive-missing detection with a one-click download button, on both
  the create and join paths. The one un-automatable click ("Add shortcut to
  Drive") is stated honestly on screen, not hidden.
- Multiple worlds: config schema v2, world switcher menu on the main
  screen, per-world sync state and backups. Your single-world config
  migrated automatically — verified against your actual files.

**Tier A — all seven**
- Live presence (`playing.json`): "Bram is in the wilds right now" in the
  hero *and* a hard confirm if you hit Play anyway. Stale after 4 h so a
  crash can't block the group. Cleared when the save is shared.
- System tray: close-to-tray (toggle in Settings), "your turn" tray
  notification when any configured world gets a new save, `--tray` quiet
  start.
- Generic webhooks per world (Discord/Slack payloads auto-detected, plain
  text for ntfy.sh and anything else). Fire-and-forget; can never fail a sync.
- Backup browser (world menu → Backups) with one-click restore. Restores
  are themselves backed up (`pre_restore`), so it's reversible; restore is
  local-only and you share it explicitly afterwards — the conflict checks
  stay in the loop.
- Session notes: optional one-liner after each share, shown italic in the
  feed. Skippable, auto-skips after 60 s, capped at 200 chars.
- Auto-detect game install: Steam registry + libraryfolders.vdf scan
  (Settings → Auto-detect install). Steam-URI launch remains the default.
- About screen with version, changelog, and the quiet "Forged by MrNothing"
  line at the bottom. Nowhere else.

**Tier B — 4 of 6 shipped**
- Personalization: emblem (emoji) + color per player, shown on feed avatars.
- Session duration: measured launch→close, shown in the feed ("2.2 h session").
- Turn reservation: "I've got next" button + claim shown to everyone;
  claims expire after 12 h; consumed automatically when the claimant plays.
- Launch with Windows: Settings toggle (packaged exe only), starts in tray.
- Version-mismatch warning: manifests now carry `app_schema`; if a friend's
  newer app bumps it, older apps show "This world needs a newer app" and
  disable Play instead of failing weirdly.
- **Deferred:** screenshot-on-push and *cumulative* per-person stats — see
  judgment calls below.

**Tier C — design notes only, as instructed** (bottom of this file).

### Judgment calls worth double-checking

1. **Your player name migrated as-is** (it's whatever you had in the v1
   config). Settings → Your name if you want to change what friends see.
2. **Close button hides to tray by default** (that's what makes "toast when
   it's your turn" work without keeping a window open). Quit is in the tray
   menu; toggle the behavior in Settings if it annoys you.
3. **Save folder and exe path are global, not per-world** — the game writes
   every world's `.sav` to the same SaveGames folder, so per-world copies
   would just be confusing duplication.
4. **Invite codes carry the share link** (so joining is one paste). That
   means the code itself grants folder access to whoever has it — same
   trust level as the Drive link, fine for a friend group. Codes without a
   link work too (friend must be added to the folder manually).
5. **Webhook message fires immediately on share, without the session note**
   (the note is typed after). Felt better than delaying the ping.
6. **Session-note prompt only appears if the window is visible** — no
   overlay ambushes from the tray.
7. **Presence is advisory, not a lock.** It warns before Play; the sync
   core's conflict detection remains the actual guarantee. A stale marker
   (crash, killed app) expires after 4 h and can never block anyone.
8. **Screenshot-on-push: deferred.** The push happens *after* the game
   closes, so a screenshot then shows your desktop, not the world. Doing it
   honestly means periodic capture *while* in-game (fullscreen capture is
   unreliable, adds shared-folder bloat, and is exactly the kind of feature
   that destabilizes the play flow at 4 a.m.). Design sketch in Tier C notes.
9. **Cumulative stats: partially deferred.** Session lengths shipped in the
   feed. "Total sessions/hours per person" needs a separate accumulator
   file (history caps at 50 entries, so summing it would silently lie);
   that's a small, safe follow-up but it lost the priority contest tonight.
10. **v1.0 ↔ v1.1 compatibility:** v1.0 apps read v1.1 manifests fine
    (extra fields are ignored) and vice versa. But v1.0 friends won't see
    presence warnings or get tray pings — nudge everyone to update.
11. **The sync core was never touched** except for two additive,
    test-covered helpers: `amend_history_entry` (whitelisted metadata on
    existing history entries) and the `app_schema` stamp on push. All 15
    original protocol tests pass unmodified (they're now part of 52).

---

## Judgment calls & decisions (running log)

### Build order
Multi-world refactor came **before** invite codes, because "Join a world"
creates a world entry — the config model had to support a list first. Sync
core (`app/core/sync.py`) stayed frozen; everything new goes through additive
helpers or new modules (`config`, `invite`, `presence`, `webhook`, `clouds`,
`steam`, `autostart`, `backups`).

### Config schema v2
- `player_name`, save folder, exe path stay **global**; each world gets
  `sync_dir`, `share_link`, `webhook_url`. The game writes all worlds' saves
  into one folder, so per-world save dirs would be duplicated confusion.
- Migration keeps `config.v1.bak` / `state.v1.bak`. Migration is idempotent
  (verified: second launch doesn't re-migrate).
- The sync core still receives the v1-shaped flat dict via
  `config.effective_cfg()` — that boundary is the whole trick.

### Invite mechanics
- We cannot mint Drive share links without OAuth + a verified Google Cloud
  app, which violates the no-backend spirit and is a weeks-long yak. So the
  host pastes the link once per world; it's remembered; every later invite
  is one click. The joiner's floor is Google's own "Add shortcut to Drive"
  consent — stated on-screen instead of papered over.
- The join watcher scans the *top level* of every detected cloud root
  (OneDrive env vars, `~/Dropbox`, `~/Google Drive`, every `X:\My Drive`)
  every 2.5 s. Drive shortcuts land at My Drive root, so top-level is the
  right depth; "Browse for it manually" covers exotic setups.
- Folder match requires the manifest's `world_name` to agree (or no
  manifest yet) — prevents grabbing an identically-named folder from some
  other group.

### Tray & lifecycle
- `QApplication.setQuitOnLastWindowClosed(False)` + explicit quit paths.
  Closing mid-session while tray is enabled just hides (watcher keeps
  running — that's the *good* case); actually quitting mid-session still
  triggers the "auto-share won't happen" confirm.

### Testing approach
- Everything headless-testable is tested (protocol, migration, invites,
  presence, webhooks, backups: 52 tests). UI is exercised by the screenshot
  harness, which builds every screen with real data and caught real bugs
  again tonight (it found the join watcher working *too* well — it detected
  your actual Drive folder and completed the join flow).

---

## Tier C design notes (not built, by instruction)

### Real in-game stats from the .sav file
The save is an Unreal Engine `.sav` (GVAS format, likely compressed chunks).
Day count / character level are probably in there as tagged properties, but:
the schema is undocumented, changes with game updates, and Jagex has been
patching actively. If ever attempted: a separate `savparse` module that
(1) opens the file strictly read-only, (2) runs in a subprocess with a
timeout so a parser hang/crash can't touch the app, (3) treats every field
as optional, (4) is feature-flagged off by default. A parsing bug must never
be *able* to write — enforce by never importing it anywhere near the sync
path. Verdict: fun spike for a rainy weekend, not a feature to promise.

### World branching ("sandbox copy, merge later")
Cheap version that fits the current model: "Branch off" = create a new
world entry whose `sync_dir` is a fresh subfolder, seeded by copying the
current files + a v1 manifest. That part is a day's work. The trap is the
word "merge": UE saves aren't mergeable — a "merge back" is really "pick a
winner and overwrite", which needs brutal honesty in the UI ("replace the
main world with this branch — the main world's progress since the split is
lost"). Recommend shipping it as "Fork world" + "Promote branch to main
(replaces main)" with the usual backup + double confirm, and never using
the word merge.

### Phone status page
No backend allowed — but the shared folder *is* hosted storage the whole
group can already read. Write a small static `status.html` into the shared
folder on every push/presence change (who's playing, latest version, last
few sessions); anyone can open that file from the Google Drive phone app.
Zero servers, surprisingly close to a real status page. ~Half a day, low
risk. My pick for the next nice-to-have.

### Thematic flourishes
A short ember-crackle on Play and a subtle glow sweep on "You're up to
date" would land well; Qt can do both (QSoundEffect + a QVariantAnimation
on the hero glow). Gate any sound behind a Settings toggle, default off —
launcher apps that make noise uninvited get uninstalled.

---

*Forged overnight. The wilds were quiet.* 🐉
