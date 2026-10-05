# Privacy

WorldSync is free and has no accounts. Your saves only ever go to the cloud
folder you pick. The one other thing it sends is **anonymous reports**, so I
can see which games work for real groups and fix the ones that don't.

## Turning reports off

Reports are on by default. Untick **Settings → Send anonymous reports** and
nothing more is sent. **Settings → Delete my reports** erases everything your
PC has sent so far and gives it a fresh random id.

## What a report contains

- A random id made on your PC the first time WorldSync starts. It isn't
  your Steam id, your name or your PC's name, and it isn't linked to anything.
- The app version and the Windows version (for example "Windows 11").
- Which game, and what happened: a world was set up or joined, a share or
  pull worked or failed and why (a short code like `pushed` or `wrong_game`),
  the game started or didn't, a setup step was reached.
- Numbers: how long a session lasted in minutes, the world's size in MB and
  number of files, how long a share or pull took, and how many different
  players have shared that world.
- The kind of cloud drive the shared folder is in: Google Drive, Dropbox,
  OneDrive or "other". Never the folder itself.
- Your system language code, for example `nl_NL`.
- Clicks on a few buttons: an invite code made, a checkpoint, a restore, a
  setup guide opened, the coffee link, "missing a game".
- If you answer "Did it work?": thumbs up or down, and the comment you typed
  yourself, if any.
- If the app crashes: the type of error (for example `KeyError`) and the
  name of the function it happened in. Never the error message, because
  messages can contain file paths.

The full list of allowed fields is in
[`app/core/telemetry.py`](app/core/telemetry.py). Anything else is dropped
before sending, and a test checks that names, world names and paths can't
get through.

## What is never sent

Your name or player name, friends' names, world names, file or folder paths,
invite codes, share links, save contents, or anything about your location.

## Where it goes and how long it stays

Reports go to a small database on Supabase (hosted in the EU, London region).
The key inside the app can only add reports; it can't read any back. Like most
web services, Supabase's servers see your IP address when a report arrives
and keep it briefly in their request logs; WorldSync does not store it. Reports
older than 12 months are deleted automatically every night.

Only the maintainer ([AndorManu](https://github.com/AndorManu)) can see the
results, and only as totals and anonymous lists. Nothing is sold or shared.

Questions: open an [issue](https://github.com/AndorManu/worldsync/issues).
