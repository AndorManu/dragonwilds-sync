"""Point the next build at a download channel: github (default) or nexus.

    python tools/set_channel.py nexus     # before building WorldSync-Nexus.exe
    python tools/set_channel.py github    # back to normal
"""

import re
import sys
from pathlib import Path

CHANNEL_FILE = Path(__file__).resolve().parent.parent / "app" / "channel.py"
CHANNELS = ("github", "nexus")


def main():
    channel = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    if channel not in CHANNELS:
        raise SystemExit(f"usage: set_channel.py {{{'|'.join(CHANNELS)}}}")
    text = CHANNEL_FILE.read_text(encoding="utf-8")
    text = re.sub(r'^CHANNEL = "[a-z]+"$', f'CHANNEL = "{channel}"', text, count=1, flags=re.M)
    CHANNEL_FILE.write_text(text, encoding="utf-8", newline="\n")
    print("channel:", channel)


if __name__ == "__main__":
    main()
