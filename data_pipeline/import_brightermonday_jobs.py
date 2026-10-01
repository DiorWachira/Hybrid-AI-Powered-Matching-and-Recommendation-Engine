"""Normalize a locally saved BrighterMonday/Apify JSON export for this project.

This importer does not scrape jobs or require a paid API key. It transforms an
export the researcher has permission to use into the canonical jobs JSON schema.
"""
from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path
from typing import Any


def _pick(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = re.split(r"[,;|]", value)
    elif isinstance(value, list):
        values = [str(item.get("name") or item.get("label") or "") if isinstance(item, dict) else str(item) for item in value]
    else:
        return []
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def normalize_job(record: dict[str, Any]) -> dict[str, Any]:
    title = str(_pick(record, "title", "jobTitle", "job_title", "position", default="")).strip()
    description = str(_pick(record, "description", "jobDescription", "job_description", "details", default="")).strip()
    company = _pick(record, "company_name", "companyName", "company", "employer", "organization", default="")
    if isinstance(company, dict):
        company = _pick(company, "name", "title", default="")
    if len(title) < 2 or len(description) < 20:
        raise ValueError("each job needs a title (at least 2 characters) and description (at least 20 characters)")
    stable_key = str(_pick(record, "id", "jobId", "job_id", "url", default=f"{title}|{description[:120]}"))
    salary = _pick(record, "salary_range_max", "salaryMax", "salary_max", "maxSalary", "salary")
    if isinstance(salary, dict):
        salary = _pick(salary, "max", "maximum", "to")
    salary_values = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", str(salary)) if salary is not None else []
    salary_max = max((float(value.replace(",", "")) for value in salary_values), default=None)
    experience = _pick(record, "required_experience_years", "experienceYears", "experience_years", "minimumExperience", default=0)
    experience_match = re.search(r"\d+", str(experience))
    return {
        "job_id": str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key)),
        "title": title,
        "company_name": str(company).strip() or "BrighterMonday employer",
        "specialisation": str(_pick(record, "specialisation", "specialization", "category", default="general")),
        "location": str(_pick(record, "location", "city", "region", default="Kenya")),
        "required_experience_years": int(experience_match.group()) if experience_match else 0,
        "required_skills": _strings(_pick(record, "required_skills", "skills", "requirements", "qualifications")),
        "mandatory_certifications": _strings(_pick(record, "mandatory_certifications", "certifications", "certificates")),
        "salary_range_max": salary_max,
        "description": description,
        "source": "BrighterMonday Kenya export",
    }


def normalize_export(source: Path) -> list[dict[str, Any]]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    records = payload.get("jobs", payload.get("data", [])) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("export must contain a list of jobs or a top-level jobs/data list")
    return [normalize_job(item) for item in records if isinstance(item, dict)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="local JSON export")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "dataset" / "brightermonday_jobs.json")
    args = parser.parse_args()
    jobs = normalize_export(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    print(f"Normalized {len(jobs)} jobs into {args.output}")


if __name__ == "__main__":
    main()
