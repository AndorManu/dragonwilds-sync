# Notes for Manu — overnight build, 2026-07-08 → 09

*(Summary section will be written at the top when the night's work is done.
Below it: a running log of judgment calls, in the order I made them.)*

---

## Judgment calls & decisions (running log)

### Build order
Multi-world refactor comes **before** invite codes, because "Join a world"
creates a world entry — the config model has to support a list first. Sync
core (`app/core/sync.py`) stays frozen; everything new goes through additive
helpers or new modules, so the v1 correctness guarantees can't regress.

### Config schema v2
- `player_name`, the game save folder, and the exe path stay **global** (one
  game install, one save folder per machine); each world gets its own
  `sync_dir`, plus per-world `share_link` and `webhook_url`. Reasoning: the
  game writes all worlds' `.sav` files into the same SaveGames folder, so a
  per-world save dir would just be duplicated confusion.
- Migration keeps a backup of the old file as `config.v1.bak` /
  `state.v1.bak` in `%APPDATA%\DragonwildsSync`, so rollback is trivial.
