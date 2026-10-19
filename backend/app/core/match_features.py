"""Shared training/serving feature contracts. Both sides import this one file, so they cannot drift.

A model artifact names the contract it was trained on; serving computes exactly that contract.
"""
import hashlib
import json
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

FEATURE_ORDER = ["S_bert", "S_graph", "S_growth"]
CONTRACT_V1 = "serving-direct-skill-growth-v1"
CONTRACT_V2 = "serving-related-skill-readiness-v2"
SUPPORTED_CONTRACTS = (CONTRACT_V1, CONTRACT_V2)
# Contract used by new training runs unless one is requested explicitly.
FEATURE_CONTRACT = CONTRACT_V1

# Versioned skill graph used by the v2 skill feature. Scoring reads this file, never live Neo4j, so a score
# is reproducible and an admin ontology edit cannot silently change a trained model's inputs.
SKILL_RELATIONS_PATH = Path(__file__).resolve().parents[3] / "data_pipeline" / "ontology" / "curated_skill_relationships.json"
MAX_RELATION_HOPS = 2
# Experience beyond this multiple of the posted minimum adds no further readiness.
EXPERIENCE_CAP = 1.5


def skill_overlap(candidate_skills: Iterable[str], required_skills: Iterable[str]) -> float:
    candidate = {skill.casefold() for skill in candidate_skills}
    required = {skill.casefold() for skill in required_skills}
    return len(candidate & required) / len(required) if required else 0.0


def growth_score(years_experience: int, required_experience_years: int, certification_count: int) -> float:
    experience = min(years_experience / max(required_experience_years, 1), 1.0)
    return (experience + min(certification_count / 2, 1.0)) / 2


@lru_cache(maxsize=4)
def _relations(path: str, mtime_ns: int) -> tuple[dict[str, dict[str, float]], str]:
    content = Path(path).read_bytes()
    graph: dict[str, dict[str, float]] = {}
    for entry in json.loads(content):
        source = str(entry["name"]).strip().casefold()
        for related in entry.get("related", []):
            target = str(related["name"]).strip().casefold()
            weight = max(0.0, min(1.0, float(related.get("weight", 0.5))))
            if source == target or weight == 0:
                continue
            # Relationships are treated as undirected: knowing either side is evidence for the other.
            for left, right in ((source, target), (target, source)):
                graph.setdefault(left, {})
                graph[left][right] = max(graph[left].get(right, 0.0), weight)
    return graph, hashlib.sha256(content).hexdigest()


def skill_relations() -> tuple[dict[str, dict[str, float]], str]:
    """The relation graph (casefolded skill -> neighbour -> weight) and the SHA-256 of its source file."""
    return _relations(str(SKILL_RELATIONS_PATH), SKILL_RELATIONS_PATH.stat().st_mtime_ns)


def skill_credits(candidate_skills: Iterable[str], required_skills: Iterable[str], graph: dict[str, dict[str, float]] | None = None) -> list[tuple[str, float, str | None]]:
    """For each required skill: (skill, credit, evidence). Exact matches earn 1; otherwise the strongest
    path of at most two relationships from any listed skill earns the product of its weights."""
    graph = skill_relations()[0] if graph is None else graph
    held = {skill.strip().casefold(): skill.strip() for skill in candidate_skills if skill.strip()}
    credits = []
    for required in dict.fromkeys(skill.strip() for skill in required_skills if skill.strip()):
        key = required.casefold()
        if key in held:
            credits.append((required, 1.0, held[key]))
            continue
        best, evidence = 0.0, None
        frontier = {key: 1.0}
        for _ in range(MAX_RELATION_HOPS):
            reached: dict[str, float] = {}
            for node, strength in frontier.items():
                for neighbour, weight in graph.get(node, {}).items():
                    reached[neighbour] = max(reached.get(neighbour, 0.0), strength * weight)
            for node, strength in reached.items():
                if node in held and (strength > best or (strength == best and evidence is not None and held[node] < evidence)):
                    best, evidence = strength, held[node]
            frontier = reached
        credits.append((required, round(best, 6), evidence))
    return credits


def related_skill_overlap(candidate_skills: Iterable[str], required_skills: Iterable[str], graph: dict[str, dict[str, float]] | None = None) -> float:
    credits = skill_credits(candidate_skills, required_skills, graph)
    return sum(credit for _, credit, _ in credits) / len(credits) if credits else 0.0


def experience_readiness(years_experience: int, required_experience_years: int) -> float:
    # Mandatory certifications are a hard eligibility rule, so every scored candidate already holds them;
    # unlike v1, readiness does not penalise candidates for jobs that require no certification.
    return min(years_experience / max(required_experience_years, 1), EXPERIENCE_CAP) / EXPERIENCE_CAP


def contract_features(contract: str, *, candidate_skills: Iterable[str], required_skills: Iterable[str], years_experience: int, required_experience_years: int, certification_count: int) -> tuple[float, float]:
    """(S_graph, S_growth) for the named contract; S_bert is computed by the encoder."""
    if contract == CONTRACT_V1:
        return skill_overlap(candidate_skills, required_skills), growth_score(years_experience, required_experience_years, certification_count)
    if contract == CONTRACT_V2:
        return related_skill_overlap(candidate_skills, required_skills), experience_readiness(years_experience, required_experience_years)
    raise ValueError(f"Unsupported feature contract: {contract}")
