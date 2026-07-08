"""Webhook payload shaping per service."""

import json

from app.core.webhook import build_request


def test_discord_payload():
    req = build_request("https://discord.com/api/webhooks/123/abc", "hello")
    assert json.loads(req.data) == {"content": "hello"}
    assert req.get_header("Content-type") == "application/json"


def test_slack_payload():
    req = build_request("https://hooks.slack.com/services/T/B/x", "hello")
    assert json.loads(req.data) == {"text": "hello"}


def test_plain_payload_for_everything_else():
    req = build_request("https://ntfy.sh/my-topic", "Andor shared v15")
    assert req.data == b"Andor shared v15"
    assert req.get_header("Content-type").startswith("text/plain")
    assert req.get_method() == "POST"
