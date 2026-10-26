import threading
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.db import graph_sync
from app.schemas import LoginRequest


def test_sign_in_accepts_stored_reserved_domain_addresses():
    assert LoginRequest(email="seed-candidate-abc@jobbridge.local", password="x").email == "seed-candidate-abc@jobbridge.local"
    with pytest.raises(ValidationError):
        LoginRequest(email="not-an-email", password="x")


def _run_once(monkeypatch, sync):
    stop = threading.Event()
    driver = MagicMock()
    monkeypatch.setattr(graph_sync, "get_neo4j_driver", MagicMock(return_value=driver))
    monkeypatch.setattr(graph_sync, "ensure_graph_schema", MagicMock())
    monkeypatch.setattr("app.db.postgres.SessionLocal", MagicMock())

    def tick(*_):
        stop.set()
        return sync()
    monkeypatch.setattr(graph_sync, "sync_graph_events", tick)
    graph_sync.run_sync_loop(stop, interval_seconds=0)
    return driver


def test_worker_drains_outbox_and_closes_driver_on_stop(monkeypatch):
    driver = _run_once(monkeypatch, lambda: 3)
    graph_sync.ensure_graph_schema.assert_called_once_with(driver)
    driver.close.assert_called_once()


def test_worker_survives_a_failed_tick(monkeypatch):
    def fail():
        raise RuntimeError("neo4j down")
    driver = _run_once(monkeypatch, fail)
    driver.close.assert_called_once()


def test_worker_is_off_in_tests():
    from app.config import get_settings
    assert get_settings().graph_sync_interval_seconds == 0
