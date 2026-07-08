# Changelog

## 1.3.0 — 2026-07-09

**Your characters join the story.**

- **Characters page** (world menu): everyone on this PC with procedural
  portraits drawn from their actual in-game appearance, real playtime,
  vitals, and per-session vault backups + named checkpoints.
- **Portraits as avatars**: the session feed and live presence now show who
  played *as whom* — "Bram is in the wilds as Grimjaw", portrait included.
  Friends see it too (a tiny appearance descriptor rides the manifest).
- **Character travel**: mark a character as travelling and it follows you
  between your own PCs through the shared folder — with the same conflict
  protection as world saves (it literally reuses the same protocol).
- **The Saga** (world menu): the fellowship's totals (all-time, via a small
  accumulator in the shared folder) and a chronicle of everyone's session
  notes, exportable as a handsome `saga.html` for the group.
- **Group history**: the last three shared world versions are archived in
  the shared folder — anyone can roll the group back from Backups.
- **Extras**: per-world banner colors, a soft ember chime on Play (off in
  Settings if it's not your thing), and optional Discord Rich Presence.
- *…and the dragon's eye keeps a secret. Curious fingers find it.*

Character files are only ever edited checkpoint-first, with the game's own
`.backup` twin untouched. Sync protocol: unchanged, compatible with 1.0–1.2.

## 1.2.0 — 2026-07-09

**A new look, and a lot less friction.**

- Complete visual redesign into a dark-fantasy game launcher: a procedurally
  painted, per-world hero banner (moonlit ridges + drifting embers, tinted
  per world), the world name set in Cinzel Decorative, an ember-gold accent
  alongside the emerald, and a showpiece PLAY button that breathes at rest.
  Bundled Cinzel / EB Garamond display type.
- **One-click auto-update through the shared folder.** The host publishes a
  build (Settings → Publish this version); everyone else gets an update bar
  and updates in place. No store, no server, no manual exe-swapping.
- **“Test my setup”** — a friendly checklist that catches setup snags
  (folders, cloud sync, game launch) before they bite.
- **Named checkpoints** — snapshot your save before something risky and
  restore it any time, alongside the automatic overwrite-backups.
- **Pass the turn** — hand a specific friend the world; they get a tray ping.
- **Save safety** — a corrupt or still-downloading save is never shared, so
  one bad file can't poison the group.
- Optional phone-checkable `status.html` written into the shared folder.
- Richer conflict prompt showing both saves' sizes and times.

The sync protocol is unchanged and fully compatible with 1.0 and 1.1.

## 1.1.0 — 2026-07-09

**Joining is now one code.** A friend pastes an invite code, clicks the share
link it opens, adds the folder to their Drive — the app spots it syncing in
and finishes setup by itself.

- Invite codes (generated and decoded entirely locally — no backend)
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

## 1.0.0 — 2026-07-08

First release: pull → play → share with a version counter, conflict detection
on both pull and push, atomic manifest writes, and automatic safety backups.
