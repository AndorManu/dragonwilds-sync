# Changelog

## 2.1.0 - unreleased

**Find out what actually works.**

- Anonymous reports, on by default and switched off with one checkbox in
  Settings, plus a "did it work?" after each game's first share, so beta games
  can be fixed and marked tested. Never names, world names, folders or saves.
- A small "Buy me a coffee" link at the bottom of every screen, and one
  Windows notification after your fifth share. No pop-ups.
- Reports go to a small database that only accepts new rows; nothing can be
  read back with the key inside the app.
- PRIVACY.md, automatic deletion after 12 months, and Settings → "Delete my
  reports" to erase everything a PC has sent.
- Crash reports (error type and function only) and timing numbers, so problems
  show up before anyone has to file an issue.

## 2.0.0 - 2026-10-05

**Dragonwilds Sync is now WorldSync.**

- Ten games: RuneScape: Dragonwilds, Valheim, Enshrouded, Palworld, Core
  Keeper, Sons of the Forest, V Rising, Grounded, Raft and 7 Days to Die.
  Dragonwilds is tested; the others are marked beta until real groups have
  played them for a while.
- A game library is the new home screen. Adding a game opens a picker with
  the games installed through Steam at the top.
- Every game has its own palette, typefaces and animated banner.
- A step-by-step setup guide for every game, in the app and in docs/GAMES.md.
- Setup finds each game's save folder and lists its worlds by when they were
  last played, with the game's known quirks shown before the first share.
- Folder-based worlds sync as a whole, including nested files and autosaves
  the game rotates out; their change detection covers every file.
- The shared folder now records which game it belongs to, and WorldSync
  refuses to pull or push a world into a different game.
- Invite codes carry the game. Dragonwilds codes keep the old `DWS1.` format
  so friends on 1.x can still join.
- Upgrading: settings, worlds and backups are copied from
  `%APPDATA%\DragonwildsSync` on first start (the old folder is left alone),
  and the config moves to schema 3 with a `config.v2.bak` kept.
- Fixed: a missing import in the controller.
- Sync protocol unchanged for Dragonwilds worlds; manifests gain an optional
  `game` field that older versions ignore.

## 1.3.2 - 2026-10-05

Housekeeping only. In-app changelog caught up, README and UI wording
cleaned up, screenshots re-rendered for the current version. No functional
changes; sync protocol unchanged.

## 1.3.1 - 2026-09-21

**Out in the open.**

- First public release on GitHub, MIT licensed.
- Every release exe is now built by GitHub Actions from the tagged source;
  the SHA-256 is printed in the build log.
- Tests run in CI on Windows and Linux.
- README rewritten around the actual problem: a world tied to one PC.
- No functional changes; sync protocol unchanged, compatible with 1.0-1.3.

## 1.3.0 - 2026-07-09

**Your characters join the story.**

- **Characters page** (world menu): everyone on this PC with procedural
  portraits drawn from their actual in-game appearance, real playtime,
  vitals, and per-session vault backups + named checkpoints.
- **Portraits as avatars**: the session feed and live presence now show who
  played *as whom* - "Bram is in the wilds as Grimjaw", portrait included.
  Friends see it too (a tiny appearance descriptor rides the manifest).
- **Character travel**: mark a character as travelling and it follows you
  between your own PCs through the shared folder - with the same conflict
  protection as world saves (it literally reuses the same protocol).
- **The Saga** (world menu): the fellowship's totals (all-time, via a small
  accumulator in the shared folder) and a chronicle of everyone's session
  notes, exportable as a handsome `saga.html` for the group.
- **Group history**: the last three shared world versions are archived in
  the shared folder - anyone can roll the group back from Backups.
- **Extras**: per-world banner colors, a soft ember chime on Play (off in
  Settings if it's not your thing), and optional Discord Rich Presence.
- *…and the dragon's eye keeps a secret. Curious fingers find it.*

Character files are only ever edited checkpoint-first, with the game's own
`.backup` twin untouched. Sync protocol: unchanged, compatible with 1.0-1.2.

## 1.2.0 - 2026-07-09

**A new look, and a lot less friction.**

- Complete visual redesign into a dark-fantasy game launcher: a procedurally
  painted, per-world hero banner (moonlit ridges + drifting embers, tinted
  per world), the world name set in Cinzel Decorative, an ember-gold accent
  alongside the emerald, and a showpiece PLAY button that breathes at rest.
  Bundled Cinzel / EB Garamond display type.
- **One-click auto-update through the shared folder.** The host publishes a
  build (Settings → Publish this version); everyone else gets an update bar
  and updates in place. No store, no server, no manual exe-swapping.
- **“Test my setup”** - a friendly checklist that catches setup snags
  (folders, cloud sync, game launch) before they bite.
- **Named checkpoints** - snapshot your save before something risky and
  restore it any time, alongside the automatic overwrite-backups.
- **Pass the turn** - hand a specific friend the world; they get a tray ping.
- **Save safety** - a corrupt or still-downloading save is never shared, so
  one bad file can't poison the group.
- Optional phone-checkable `status.html` written into the shared folder.
- Richer conflict prompt showing both saves' sizes and times.

The sync protocol is unchanged and fully compatible with 1.0 and 1.1.

## 1.1.0 - 2026-07-09

**Joining is now one code.** A friend pastes an invite code, clicks the share
link it opens, adds the folder to their Drive - the app spots it syncing in
and finishes setup by itself.

- Invite codes (generated and decoded entirely locally - no backend)
- "Create a world / Join a world" onboarding fork
- Google-Drive-missing detection with a one-click download prompt
- Multiple worlds, with a switcher on the main screen; v1 configs migrate
  automatically (old files kept as `*.v1.bak`)
- Live presence: see "Bram is in the wilds right now" *before* you hit Play
- Turn claims: a lightweight "I've got next"
- System tray: close-to-tray, "your turn" notifications, quiet `--tray` start
- Per-world webhook notifications (Discord / Slack / ntfy.sh)
- Backup browser with one-click, reversible restore
- Session notes ("What happened this session?") and session lengths in the feed
- Per-player emblem + color in the feed
- Auto-detect the game install from the Steam library
- Start-with-Windows toggle
- Version-mismatch warning if a friend's newer app changes the manifest format
- About screen with changelog

Sync protocol: unchanged and fully compatible with 1.0.0. New manifest fields
are optional; 1.0.0 apps read 1.1.0 manifests fine (they just don't show the
new toys).

## 1.0.0 - 2026-07-08

First release: pull → play → share with a version counter, conflict detection
on both pull and push, atomic manifest writes, and automatic safety backups.
