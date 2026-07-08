# Changelog

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
