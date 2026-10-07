"""Print the CHANGELOG.md section for one version, for the GitHub release text.

    python tools/release_notes.py 2.1.2 > notes.md

The app shows the first line of these notes in its "Update & restart" prompt.
"""

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def section(version: str, text: str) -> str:
    version = version.lstrip("v")
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = re.match(rf"^## {re.escape(version)}\b", line) is not None
            continue
        if inside:
            out.append(line)
    return "\n".join(out).strip()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: release_notes.py <version>")
    notes = section(sys.argv[1], CHANGELOG.read_text(encoding="utf-8"))
    print(notes or f"WorldSync {sys.argv[1].lstrip('v')}")


if __name__ == "__main__":
    main()
