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
