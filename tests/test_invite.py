"""Invite code round-trip and failure modes."""

import pytest

from app.core.invite import InviteError, decode, encode


def test_round_trip_with_link():
    code = encode("Minhalla", "Dragonwilds Sync",
                  "https://drive.google.com/drive/folders/abc123?usp=sharing")
    data = decode(code)
    assert data["world_name"] == "Minhalla"
    assert data["folder_name"] == "Dragonwilds Sync"
    assert data["share_link"].startswith("https://drive.google.com/")


def test_round_trip_without_link():
    data = decode(encode("Minhalla", "DW", None))
    assert data["share_link"] is None


def test_whitespace_and_newlines_tolerated():
    code = encode("Minhalla", "Dragonwilds Sync", "https://x.example/f")
    mangled = "  " + code[:10] + "\n" + code[10:20] + " " + code[20:] + "\r\n"
    assert decode(mangled)["world_name"] == "Minhalla"


def test_unicode_world_names_survive():
    data = decode(encode("Драконьи земли 🐉", "Sync", None))
    assert data["world_name"] == "Драконьи земли 🐉"


@pytest.mark.parametrize("bad", [
    "", "   ", "hello there", "DWS1.", "DWS1.!!!not-base64!!!",
    "DWS9." + "AAAA", "x" * 3000,
])
def test_garbage_rejected_with_friendly_error(bad):
    with pytest.raises(InviteError):
        decode(bad)


def test_tampered_payload_rejected():
    code = encode("Minhalla", "DW", "https://x.example")
    tampered = code[:-4] + ("AAAA" if not code.endswith("AAAA") else "BBBB")
    with pytest.raises(InviteError):
        decode(tampered)
