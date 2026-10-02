"""Rebuildable Neo4j projections driven by committed PostgreSQL outbox events."""
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Candidate, Employer, GraphSyncEvent, JobApplication, JobPosting
from app.db.neo4j_db import get_neo4j_driver

CONSTRAINTS = (
    "CREATE CONSTRAINT candidate_id_unique IF NOT EXISTS FOR (node:Candidate) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT job_id_unique IF NOT EXISTS FOR (node:Job) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT skill_name_unique IF NOT EXISTS FOR (node:Skill) REQUIRE node.name IS UNIQUE",
    "CREATE CONSTRAINT certification_name_unique IF NOT EXISTS FOR (node:Certification) REQUIRE node.name IS UNIQUE",
    "CREATE CONSTRAINT industry_name_unique IF NOT EXISTS FOR (node:Industry) REQUIRE node.name IS UNIQUE",
)


def ensure_graph_schema(driver) -> None:
    with driver.session(database="neo4j") as graph:
        for statement in CONSTRAINTS:
            graph.run(statement).consume()


def _replace_edges(transaction, label, identifier, relation, target_label, names):
    transaction.run(
        f"MATCH (node:{label} {{id: $id}})-[edge:{relation}]->() DELETE edge",
        id=identifier,
    ).consume()
    for name in sorted({value.strip().casefold() for value in names if value.strip()}):
        existing = transaction.run(
            f"MATCH (target:{target_label}) WHERE toLower(trim(target.name)) = $name "
            "RETURN target.name AS name ORDER BY target.name LIMIT 1", name=name,
        ).single()
        canonical = existing["name"] if existing else name
        transaction.run(
            f"MATCH (node:{label} {{id: $id}}) MERGE (target:{target_label} {{name: $name}}) "
            f"MERGE (node)-[:{relation}]->(target)", id=identifier, name=canonical,
        ).consume()


def _project(transaction, entity_type, identifier, payload):
    if entity_type == "application":
        transaction.run("MATCH ()-[edge:APPLIED_TO {application_id: $id}]->() DELETE edge", id=identifier).consume()
        if payload is not None:
            transaction.run(
                "MERGE (candidate:Candidate {id: $candidate_id}) "
                "MERGE (job:Job {id: $job_id}) "
                "MERGE (candidate)-[edge:APPLIED_TO {application_id: $id}]->(job) "
                "SET edge.status = $status, edge.applied_at = $created_at",
                id=identifier, **payload,
            ).consume()
        return
    label = "Candidate" if entity_type == "candidate" else "Job"
    if payload is None:
        transaction.run(f"MATCH (node:{label} {{id: $id}}) DETACH DELETE node", id=identifier).consume()
        return
    transaction.run(f"MERGE (node:{label} {{id: $id}}) SET node.source = 'postgresql'", id=identifier).consume()
    _replace_edges(transaction, label, identifier, "HAS_SKILL" if entity_type == "candidate" else "REQUIRES_SKILL", "Skill", payload["skills"])
    _replace_edges(transaction, label, identifier, "HOLDS_CERTIFICATE" if entity_type == "candidate" else "REQUIRES_CERT", "Certification", payload["certifications"])
    if entity_type == "job":
        transaction.run("MATCH (node:Job {id: $id}) SET node.title = $title, node.status = $status", id=identifier, title=payload["title"], status=payload["status"]).consume()
        _replace_edges(transaction, label, identifier, "BELONGS_TO", "Industry", [payload["industry"]] if payload["industry"] else [])


def _payload(database: Session, event: GraphSyncEvent):
    if event.entity_type == "candidate":
        candidate = database.get(Candidate, event.entity_id)
        return {"skills": candidate.skills or [], "certifications": candidate.certifications or []} if candidate else None
    if event.entity_type == "job":
        job = database.get(JobPosting, event.entity_id)
        if job is None:
            return None
        employer = database.get(Employer, job.employer_id)
        return {"skills": job.required_skills or [], "certifications": job.mandatory_certifications or [], "title": job.title, "status": job.status.value, "industry": employer.industry if employer else None}
    application = database.get(JobApplication, event.entity_id)
    return {"candidate_id": str(application.candidate_id), "job_id": str(application.job_id), "status": application.status, "created_at": application.created_at.isoformat()} if application else None


def sync_graph_events(database: Session, driver, limit: int = 100) -> int:
    if not 1 <= limit <= 10000:
        raise ValueError("limit must be between 1 and 10000")
    processed = 0
    for _ in range(limit):
        with database.begin():
            if not database.scalar(text("SELECT pg_try_advisory_xact_lock(2026100205)")):
                break
            event = database.scalar(select(GraphSyncEvent).order_by(GraphSyncEvent.created_at, GraphSyncEvent.event_id).limit(1).with_for_update())
            if event is None:
                break
            with driver.session(database="neo4j") as graph:
                graph.execute_write(_project, event.entity_type, str(event.entity_id), _payload(database, event))
            database.delete(event)
        processed += 1
    return processed


def main() -> None:
    import argparse
    from app.db.postgres import SessionLocal

    parser = argparse.ArgumentParser(description="Apply committed PostgreSQL changes to Neo4j; failed events remain queued.")
    parser.add_argument("--limit", type=int, default=100)
    arguments = parser.parse_args()
    with get_neo4j_driver() as driver:
        ensure_graph_schema(driver)
        with SessionLocal() as database:
            print(f"Graph events processed: {sync_graph_events(database, driver, arguments.limit)}")


if __name__ == "__main__":
    main()