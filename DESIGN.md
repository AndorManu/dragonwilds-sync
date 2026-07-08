# Design rationale

## Stack: Python + PySide6 (Qt), PyInstaller

Three things decided it:

1. **The sync logic was already validated in Python.** Tauri/Electron would
   have meant rewriting exactly the code that was tested and correct. With
   Qt, `app/core/sync.py` is a near-verbatim port of the prototype, and the
   pytest suite pins its behavior.
2. **Qt gives full visual control** — frameless window, custom titlebar,
   real hover/pressed states, animated spinner and in-game pulse, toasts,
   an in-window modal overlay. None of that is reachable in Tkinter.
3. **PyInstaller reliably produces one double-clickable `.exe`** (44 MB,
   windowed, icon embedded). No runtime, no dependencies, no console window,
   ever. `installer.iss` is included for an optional Inno Setup wizard, but
   the bare exe is already zero-friction.

## Visual identity

- **Obsidian + dragonfire.** Near-black blue-green base (`#0C1116`), one
  emerald accent (`#3ECF8E → #1FA89B` gradient) used only for the identity
  and the primary action. Amber is reserved for "attention" (new save,
  warnings), red strictly for destructive choices. Nothing else gets color —
  that's what keeps it calm.
- **The mark is a dragon's eye** — almond outline, slit pupil, one glint —
  on a rounded-square badge. Fantasy at a glance, but geometric enough to
  sit next to Linear/Raycast without embarrassment. Generated at all icon
  sizes by `tools/generate_icon.py`.
- **Typography:** Segoe UI Variable with a spaced small-caps wordmark in the
  titlebar; 19px headline / 12.5px secondary rhythm everywhere else.
- **Frameless window** with custom titlebar, 14px radius, soft drop shadow;
  fixed launcher-size (512×784) because a relay tool has exactly one job.

## The screens

- **Onboarding** (4 short steps, under a minute): welcome → name → world
  (save folder pre-filled, worlds auto-detected from `.sav` files) → shared
  folder (detected cloud drives offered as one-click chips, folder created
  on the spot). Inline validation, no dialogs.
- **Main screen** is a hierarchy of exactly three things: a status hero
  ("You're up to date" / "New save from Elise" with version + relative
  time), a big gradient **PLAY** button with a hover glow, and the session
  feed (avatar initials, who shared which version, when). A footer dot
  quietly confirms the shared folder is reachable. During a session the
  hero morphs through checking → launching → in-game (breathing dot) →
  sharing, and the Play button narrates the same phases.
- **Settings** is the onboarding form on one page, plus "Open log folder".
- **Toasts** (bottom, auto-dismiss, click to close) carry all routine
  feedback. The **only blocking UI** is the overwrite confirmation — a
  full-window dim with the safe choice focused and the destructive one in
  red. It appears in exactly three cases: pulling over unshared local
  progress, sharing over someone's newer session, and quitting the app
  mid-game.

## Protocol notes (vs. the prototype)

Unchanged: manifest schema, version counter, `{world}*` file copying,
hash-based conflict detection, pull-before-play / push-after-quit flow.

Additions, all protocol-compatible:

- `version.json` also carries a capped `history` list → powers the session
  feed for everyone with old manifests still readable.
- The pull-side conflict check now has a **push-side mirror**: if someone
  shared while you were playing, sharing asks before replacing their
  session (the prototype only checked on pull).
- Anything about to be overwritten (either direction) is copied to
  `%APPDATA%\DragonwildsSync\backups` first (last 10 kept).
- Manifest writes are atomic (temp file + rename) so a cloud client never
  syncs a half-written `version.json`; a corrupt/deleted manifest can't
  reset the version counter backwards.

## Screenshots

| | |
|---|---|
| ![Welcome](docs/screenshots/1_onboarding_welcome.png) | ![Shared folder](docs/screenshots/3_onboarding_shared.png) |
| ![Up to date](docs/screenshots/4_main_up_to_date.png) | ![New save](docs/screenshots/5_main_new_save.png) |
| ![In game](docs/screenshots/6_main_in_game.png) | ![Conflict](docs/screenshots/9_conflict.png) |
