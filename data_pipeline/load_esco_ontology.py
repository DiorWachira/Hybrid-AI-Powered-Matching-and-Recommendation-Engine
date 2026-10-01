"""Load an ESCO skills CSV plus curated CDACC mappings into Neo4j.

Expected skills CSV columns include preferredLabel (or name/label) and optional
skillType/category. Optional relationships CSV columns: source_skill,
target_skill, weight. The curated project relationship file is always included.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.neo4j_db import load_skill_ontology  # noqa: E402

ONTOLOGY_DIR = ROOT / "data_pipeline" / "ontology"


def load_skills(csv_path: Path | None) -> list[dict[str, str]]:
    curated = json.loads((ONTOLOGY_DIR / "curated_skill_relationships.json").read_text(encoding="utf-8"))
    rows: dict[str, dict[str, str]] = {}
    for item in curated:
        name = str(item["name"]).strip()
        rows[name.casefold()] = {"name": name, "category": str(item.get("category", "General")), "source": "curated-project"}
    if csv_path:
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                normalised = {key.casefold().replace("_", ""): value for key, value in row.items() if key and value}
                name = (normalised.get("preferredlabel") or normalised.get("name") or normalised.get("label") or "").strip()
                if not name:
                    continue
                rows[name.casefold()] = {"name": name, "category": (normalised.get("skilltype") or normalised.get("category") or "ESCO skill").strip(), "source": "ESCO CSV"}
    return list(rows.values())


def load_relationships(csv_path: Path | None) -> list[dict[str, object]]:
    curated = json.loads((ONTOLOGY_DIR / "curated_skill_relationships.json").read_text(encoding="utf-8"))
    relations: dict[tuple[str, str], dict[str, object]] = {}
    for item in curated:
        for relation in item.get("related", []):
            key = (str(item["name"]), str(relation["name"]))
            relations[key] = {"from_skill": key[0], "target_skill": key[1], "weight": float(relation.get("weight", 0.5)), "source": "curated-project"}
    if csv_path:
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                normalised = {key.casefold().replace("_", ""): value for key, value in row.items() if key and value}
                source = (normalised.get("sourceskill") or normalised.get("source") or "").strip()
                target = (normalised.get("targetskill") or normalised.get("relatedskill") or normalised.get("target") or "").strip()
                if source and target:
                    weight = float(normalised.get("weight", 0.5))
                    relations[(source, target)] = {"from_skill": source, "target_skill": target, "weight": max(0.0, min(1.0, weight)), "source": "ESCO relations CSV"}
    return list(relations.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-csv", type=Path, help="trimmed ESCO skills CSV export")
    parser.add_argument("--relationships-csv", type=Path, help="normalized ESCO related-skill CSV export")
    parser.add_argument("--mapping-json", type=Path, default=ONTOLOGY_DIR / "cdacc_esco_mapping.json")
    args = parser.parse_args()
    mapping_data = json.loads(args.mapping_json.read_text(encoding="utf-8"))
    result = load_skill_ontology(load_skills(args.skills_csv), load_relationships(args.relationships_csv), mapping_data["mappings"])
    print(json.dumps(result, indent=2))
    if mapping_data.get("mapping_status"):
        print(mapping_data["mapping_status"])


if __name__ == "__main__":
    main()
