from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from app.db.neo4j_db import get_neo4j_driver, load_skill_ontology, seed_neo4j_ontology

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
    assert seed_neo4j_ontology() == summary


def test_ontology_import_is_repeatable_and_counts_standard_mappings():
    prefix = "ontology-test-" + uuid4().hex
    names = [prefix + suffix for suffix in ("-source", "-target", "-standard")]
    skills = [{"name": name, "category": "Test", "source": "test-fixture"} for name in names[:2]]
    relations = [{"from_skill": names[0], "target_skill": names[1], "weight": 0.7, "source": "test-fixture"}]
    mappings = [{"cdacc_name": names[2], "esco_skill": names[1], "source_note": "Test fixture, not an official standard"}]
    with get_neo4j_driver() as driver:
        try:
            with driver.session(database="neo4j") as graph:
                before = graph.run("MATCH (:CDACCStandard)-[edge:MAPS_TO]->(:Skill) RETURN count(edge) AS count").single()["count"]
            first = load_skill_ontology(skills, relations, mappings)
            assert first["cdacc_mappings"] == before + 1
            assert load_skill_ontology(skills, relations, mappings) == first
            with driver.session(database="neo4j") as graph:
                assert graph.run("MATCH (:Skill {name:$source})-[edge:RELATED_TO]->(:Skill {name:$target}) RETURN count(edge) AS count, max(edge.weight) AS weight", source=names[0], target=names[1]).single().data() == {"count": 1, "weight": 0.7}
        finally:
            with driver.session(database="neo4j") as graph:
                graph.run("MATCH (node) WHERE node.name IN $names DETACH DELETE node", names=names).consume()
