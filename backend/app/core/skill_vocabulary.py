"""Skills recognised in uploaded resumes.

The vocabulary starts from the curated ontology the model was trained with, so a detected skill can earn
direct or related-skill credit, and adds common IT skills that postings ask for. Detection only reports what
a resume names: it never maps one tool onto another, because the v2 feature contract credits related skills
through the ontology itself. This list is not part of the model artifact; the pinned relationship file is
only read here, never changed.
"""
import json
import re
from functools import lru_cache

from app.core.match_features import SKILL_RELATIONS_PATH

# JobBridge lists IT roles only; these ontology entries exist for older data and are not detected.
NON_IT_SKILLS = frozenset({"financial accounting", "ifrs reporting", "tax compliance", "taxation"})

ADDITIONAL_SKILLS = (
    "Agile", "Airflow", "Ansible", "Apache Spark", "C#", "C++", "Cloud Security", "CSS", "Data Visualization", "Firewalls", "GraphQL",
    "Grafana", "Hadoop", "Helm", "HTML", "Java", "Jira", "Kotlin", "MongoDB", "Network Security", "Networking", "Nginx", "Node.js",
    "PHP", "Prometheus", "Redis", "Ruby", "Scrum", "Splunk", "Stakeholder Management", "Swift", "System Design", "Testing",
)

# Other ways of writing the same skill.
SPELLINGS = {
    "REST APIs": ("rest api", "restful", "restful api", "restful apis"),
    "Power BI": ("powerbi",),
    "CI/CD": ("cicd", "ci / cd", "ci-cd"),
    "PostgreSQL": ("postgres",),
    "Node.js": ("nodejs",),
    "Data Visualization": ("data visualisation",),
    "System Design": ("systems design",),
}

# Everyday words as well as skills ("react to incidents", "excel at"), so only their capitalised form counts.
CASE_SENSITIVE = frozenset({"Dart", "Excel", "Flutter", "Helm", "React", "Selenium", "Swift"})


def _pattern(text: str, flags: int = 0) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9+#]){re.escape(text)}(?![A-Za-z0-9+#])", flags)


@lru_cache(maxsize=1)
def _vocabulary() -> tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]:
    names = set(ADDITIONAL_SKILLS)
    for entry in json.loads(SKILL_RELATIONS_PATH.read_bytes()):
        names.add(str(entry["name"]).strip())
        names.update(str(related["name"]).strip() for related in entry.get("related", []))
    return tuple(
        (name, (_pattern(name, 0 if name in CASE_SENSITIVE else re.IGNORECASE), *(_pattern(spelling, re.IGNORECASE) for spelling in SPELLINGS.get(name, ()))))
        for name in sorted(names, key=str.casefold) if name.casefold() not in NON_IT_SKILLS
    )


def detect_skills(text: str) -> list[str]:
    """The vocabulary skills a resume names, in their canonical spelling and alphabetical order."""
    return [name for name, patterns in _vocabulary() if any(pattern.search(text) for pattern in patterns)]
