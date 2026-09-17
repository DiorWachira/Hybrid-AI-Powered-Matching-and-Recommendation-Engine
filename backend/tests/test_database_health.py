from fastapi.testclient import TestClient

from app.main import app
from app.db.neo4j_db import seed_neo4j_ontology

client = TestClient(app)


def test_health_route_reports_all_databases_ok() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["postgres"] in {"ok", "healthy"}
    assert body["database"]["neo4j"] in {"ok", "healthy"}


def test_neo4j_seed_creates_core_ontology() -> None:
    summary = seed_neo4j_ontology()

    assert summary["skills"] >= 5
    assert summary["certifications"] >= 3
    assert summary["job_roles"] >= 3
    assert summary["relationships"] >= 5
