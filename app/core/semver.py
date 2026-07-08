"""Tiny semantic-version compare — no dependency, just what update checks need."""

import re

_RE = re.compile(r"^\s*v?(\d+)\.(\d+)\.(\d+)")


def parse(version: str) -> tuple[int, int, int] | None:
    if not version:
        return None
    m = _RE.match(str(version))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def is_newer(candidate: str, current: str) -> bool:
    """True if `candidate` is a strictly higher version than `current`."""
    a, b = parse(candidate), parse(current)
    if a is None or b is None:
        return False
    return a > b
