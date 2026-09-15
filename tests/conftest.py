import pytest


@pytest.fixture(autouse=True)
def disable_query_rewrite_by_default(monkeypatch):
    monkeypatch.setenv("QUERY_REWRITE_ENABLED", "false")