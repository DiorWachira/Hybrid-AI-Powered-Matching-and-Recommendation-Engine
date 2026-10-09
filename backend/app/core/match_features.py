from collections.abc import Iterable

FEATURE_ORDER = ["S_bert", "S_graph", "S_growth"]
FEATURE_CONTRACT = "serving-direct-skill-growth-v1"


def skill_overlap(candidate_skills: Iterable[str], required_skills: Iterable[str]) -> float:
    candidate = {skill.casefold() for skill in candidate_skills}
    required = {skill.casefold() for skill in required_skills}
    return len(candidate & required) / len(required) if required else 0.0


def growth_score(years_experience: int, required_experience_years: int, certification_count: int) -> float:
    experience = min(years_experience / max(required_experience_years, 1), 1.0)
    return (experience + min(certification_count / 2, 1.0)) / 2