"""Which download this build is.

The GitHub release is the default. The Nexus Mods build differs in one way:
anonymous reports start switched off, because Nexus doesn't allow tools that
send data unless it's essential. Players can still switch them on in Settings.

tools/set_channel.py rewrites CHANNEL before a Nexus build; don't edit by hand.
"""

CHANNEL = "github"

REPORTS_ON_BY_DEFAULT = CHANNEL != "nexus"

# Nexus wants its files downloaded from Nexus, so that build doesn't fetch
# new versions from GitHub unless the player switches it on.
UPDATES_ON_BY_DEFAULT = CHANNEL != "nexus"
