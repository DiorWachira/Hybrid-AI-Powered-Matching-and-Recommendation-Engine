"""Tidy names left in Neo4j by the old lowercasing projection. Explanation view only: scores read the ontology file.

Merges case duplicates (AWS/aws) onto one spelling, restores capitals where the ontology or PostgreSQL knows them, and
deletes nodes that nothing references and no ontology load created. A deleted node is rebuilt on demand if a future
candidate or job lists that name. Safe to re-run; ``--dry-run`` only reports.

    python -m app.db.graph_repair --dry-run
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Candidate, Employer, JobPosting
from app.db.neo4j_db import get_neo4j_driver

LABELS = ("Skill", "Certification", "Industry")
ONTOLOGY_FILE = Path(__file__).resolve().parents[3] / "data_pipeline" / "ontology" / "curated_skill_relationships.json"
_RELATIONSHIP_TYPE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def choose_canonical(node_names: Iterable[str], preferred: Iterable[str], usage: Counter) -> str:
    """Pick one spelling: an ontology name first, then the most used in PostgreSQL, preferring capitals over lowercase."""
    names = list(node_names)
    key = names[0].strip().casefold()
    for name in preferred:
        if name.strip().casefold() == key:
            return name.strip()
    candidates = {name.strip() for name in names} | {name for name in usage if name.casefold() == key}
    return max(candidates, key=lambda name: (usage[name], name != name.casefold(), name))


def ontology_names(path: Path = ONTOLOGY_FILE) -> list[str]:
    names: list[str] = []
    for item in json.loads(path.read_text(encoding="utf-8")):
        names.append(str(item["name"]))
        names.extend(str(relation["name"]) for relation in item.get("related", []))
    return names


def _usage(database: Session) -> dict[str, Counter]:
    usage = {label: Counter() for label in LABELS}
    for skills, certifications in database.execute(select(Candidate.skills, Candidate.certifications)):
        usage["Skill"].update(name.strip() for name in skills or [] if name.strip())
        usage["Certification"].update(name.strip() for name in certifications or [] if name.strip())
    for skills, certifications in database.execute(select(JobPosting.required_skills, JobPosting.mandatory_certifications)):
        usage["Skill"].update(name.strip() for name in skills or [] if name.strip())
        usage["Certification"].update(name.strip() for name in certifications or [] if name.strip())
    usage["Industry"].update(name.strip() for name in database.scalars(select(Employer.industry)) if name and name.strip())
    return usage


def _merge_into(transaction, label: str, canonical: str, duplicate: str) -> None:
    """Point every relationship of ``duplicate`` at ``canonical``, then delete it. Canonical's own edges win."""
    for direction, pattern, new_edge in (
        ("in", "(node:{label} {{name: $duplicate}})<-[edge:{kind}]-(other)", "(other)-[moved:{kind}]->(target)"),
        ("out", "(node:{label} {{name: $duplicate}})-[edge:{kind}]->(other)", "(target)-[moved:{kind}]->(other)"),
    ):
        arrow = "<-[edge]-(other)" if direction == "in" else "-[edge]->(other)"
        kinds = transaction.run(f"MATCH (node:{label} {{name: $duplicate}}){arrow} RETURN DISTINCT type(edge) AS kind", duplicate=duplicate).value()
        for kind in kinds:
            if not _RELATIONSHIP_TYPE.match(kind):
                raise ValueError(f"Unexpected relationship type: {kind}")
            transaction.run(
                f"MATCH {pattern.format(label=label, kind=kind)} MATCH (target:{label} {{name: $canonical}}) "
                f"WHERE other <> target MERGE {new_edge.format(kind=kind)} ON CREATE SET moved = properties(edge)",
                duplicate=duplicate, canonical=canonical,
            ).consume()
    transaction.run(f"MATCH (node:{label} {{name: $duplicate}}) DETACH DELETE node", duplicate=duplicate).consume()


def repair_graph_names(graph, database: Session, *, dry_run: bool = False) -> dict[str, int]:
    preferred = ontology_names()
    usage = _usage(database)
    report = {"merged": 0, "renamed": 0, "unused_removed": 0}
    for label in LABELS:
        groups: dict[str, list[str]] = defaultdict(list)
        for name in graph.run(f"MATCH (node:{label}) RETURN node.name AS name").value():
            groups[name.strip().casefold()].append(name)
        for names in groups.values():
            canonical = choose_canonical(names, preferred if label == "Skill" else [], usage[label])
            duplicates = [name for name in names if name != canonical]
            if not duplicates:
                continue
            report["merged"] += len(names) - 1
            report["renamed"] += canonical not in names
            if dry_run:
                print(f"{label}: {', '.join(duplicates)} -> {canonical}")
                continue

            def apply(transaction, names=names, canonical=canonical, duplicates=duplicates):
                if canonical not in names:
                    # Keep one existing node, relationships included, under the right spelling.
                    transaction.run(f"MATCH (node:{label} {{name: $old}}) SET node.name = $new", old=duplicates[0], new=canonical).consume()
                    remaining = duplicates[1:]
                else:
                    remaining = duplicates
                for duplicate in remaining:
                    _merge_into(transaction, label, canonical, duplicate)

            graph.execute_write(apply)
        # Ontology loads set a source or category; a bare node with no edges is a leftover from old demo data.
        unused = f"MATCH (node:{label}) WHERE NOT (node)--() AND node.source IS NULL AND node.category IS NULL"
        if dry_run:
            leftovers = graph.run(f"{unused} RETURN node.name AS name ORDER BY name").value()
            if leftovers:
                print(f"{label}: unused, would remove {', '.join(leftovers)}")
            report["unused_removed"] += len(leftovers)
        else:
            report["unused_removed"] += graph.run(f"{unused} WITH node, count(*) AS one DETACH DELETE node RETURN count(one) AS removed").single()["removed"]
    return report


def main() -> None:
    from app.db.postgres import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print the changes without making them")
    arguments = parser.parse_args()
    with get_neo4j_driver() as driver, driver.session(database="neo4j") as graph, SessionLocal() as database:
        report = repair_graph_names(graph, database, dry_run=arguments.dry_run)
    print(("Would change: " if arguments.dry_run else "Changed: ") + ", ".join(f"{key}={value}" for key, value in report.items()))


if __name__ == "__main__":
    main()
