# backend/conftest.py
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
# Tests must not depend on a developer's local .env. Environment variables take
# precedence over the env file, so pin the settings that change code paths.
# (Tests that need the extraction cache enable it explicitly.)
os.environ["EXTRACTION_CACHE_ENABLED"] = "false"
os.environ["CELERY_ENABLED"] = "false"
os.environ["APP_ENV"] = "development"
# Errors are copied to the database in production; tests must not reach it.
os.environ["ERROR_STORE_ENABLED"] = "false"
# Rate limiting has its own tests; elsewhere it would only make tests order-dependent.
os.environ["RATE_LIMIT_ENABLED"] = "false"


class _DiscardingTable:
    """Accepts any query chain and returns nothing."""

    data: list = []

    def __getattr__(self, name):
        return lambda *args, **kwargs: self

    def execute(self):
        return self


class _DiscardingClient:
    def table(self, name):
        return _DiscardingTable()


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_usage_recording(monkeypatch):
    """Model-call usage is recorded to the database in production; tests must
    not reach it. A test that wants to see the rows replaces _client itself."""
    import app.services.llm_usage as usage

    monkeypatch.setattr(usage, "_client", lambda: _DiscardingClient())
    monkeypatch.setattr(usage, "_table_unavailable_until", 0.0)
