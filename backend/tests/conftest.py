import os
import sys
from pathlib import Path

# Tests stub or lazily load the encoder; never start a background model load from TestClient startup.
os.environ.setdefault("PRELOAD_MATCHING_MODEL", "false")
os.environ.setdefault("GRAPH_SYNC_INTERVAL_SECONDS", "0")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(BACKEND_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT.parent))

import socket
from urllib.parse import urlsplit

import pytest


def _reachable(host: str, port: int) -> bool:
    try:
        socket.create_connection((host, port), timeout=1).close()
        return True
    except OSError:
        return False


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: needs running PostgreSQL and Neo4j; skipped when they are down unless REQUIRE_DATABASES=1")


def pytest_collection_modifyitems(config, items):
    # CI sets REQUIRE_DATABASES=1, so a broken database service fails loudly there instead of skipping.
    marked = [item for item in items if item.get_closest_marker("integration")]
    if not marked or os.environ.get("REQUIRE_DATABASES") == "1":
        return
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    settings = get_settings()
    postgres, neo4j = make_url(settings.database_url), urlsplit(settings.neo4j_uri)
    down = [name for name, host, port in (("PostgreSQL", postgres.host, postgres.port or 5432), ("Neo4j", neo4j.hostname, neo4j.port or 7687)) if not _reachable(host, port)]
    if down:
        skip = pytest.mark.skip(reason=f"{' and '.join(down)} not reachable; run `docker compose up -d postgres neo4j` (set REQUIRE_DATABASES=1 to fail instead)")
        for item in marked:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    from app.core.rate_limit import limiter
    limiter.reset()
    yield
    limiter.reset()
