"""Shared test setup.

Tests build the real app, and the real app knows the live reporting address.
This keeps every test (and CI) from sending reports: telemetry's endpoint is
blanked unless a test swaps in its own fake backend.
"""

import pytest

from app.core import telemetry


@pytest.fixture(autouse=True)
def no_live_reports(monkeypatch):
    monkeypatch.setattr(telemetry, "ENDPOINT", "")
    monkeypatch.setattr(telemetry, "API_KEY", "")
