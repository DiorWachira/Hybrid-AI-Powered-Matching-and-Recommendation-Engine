"""Generate, clean, validate, and optionally seed the Week 4 local dataset."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "data_pipeline"
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.text_preprocessing import anonymize_resume_text  # noqa: E402


def clean_candidate_for_export(row: dict[str, object]) -> dict[str, object]:
    return {
        "candidate_id": row["candidate_id"],
        "target_role": row["target_role"],
        "specialisation": row["specialisation"],
        "location": row["location"],
        "years_experience": row["years_experience"],
        "education": row["education"],
        "skills": row["skills"],
        "certifications": row["certifications"],
        "expected_salary_kes": row["expected_salary_kes"],
        "resume_text": anonymize_resume_text(str(row["resume_text"])),
    }


def clean_job_for_export(row: dict[str, object]) -> dict[str, object]:
    return {key: row[key] for key in (
        "job_id", "title", "specialisation", "location", "required_experience_years",
        "required_skills", "mandatory_certifications", "salary_range_max", "description",
    )}


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def prepare(candidates_count: int, jobs_count: int, random_seed: int, no_seed: bool, skip_graph: bool, brightermonday_export: Path | None, output_dir: Path | None = None) -> dict[str, object]:
    if candidates_count < 1 or jobs_count < 1:
        raise ValueError("candidate and job counts must be positive")
    processed_dir = output_dir if output_dir is not None else PIPELINE / "processed"
    raw_dir = processed_dir / "raw_generated"
    export_dir = processed_dir / "export"
    processed_dir.mkdir(parents=True, exist_ok=True)
    run([sys.executable, str(PIPELINE / "generate_synthetic_data.py"), "--candidates", str(candidates_count), "--jobs", str(jobs_count), "--seed", str(random_seed), "--output-dir", str(raw_dir)])

    candidates = json.loads((raw_dir / "candidates.json").read_text(encoding="utf-8"))
    jobs = json.loads((raw_dir / "jobs.json").read_text(encoding="utf-8"))
    export_dir.mkdir(parents=True, exist_ok=True)
    clean_candidates = [clean_candidate_for_export(row) for row in candidates]
    clean_jobs = [clean_job_for_export(row) for row in jobs]

    imported_jobs = None
    if brightermonday_export:
        imported_jobs = export_dir / "jobs.json"
        run([sys.executable, str(PIPELINE / "import_brightermonday_jobs.py"), str(brightermonday_export), "--output", str(imported_jobs)])
        clean_jobs = json.loads(imported_jobs.read_text(encoding="utf-8"))

    (export_dir / "candidates.json").write_text(json.dumps(clean_candidates, indent=2), encoding="utf-8")
    if imported_jobs is None:
        (export_dir / "jobs.json").write_text(json.dumps(clean_jobs, indent=2), encoding="utf-8")

    candidate_ids = [row["candidate_id"] for row in clean_candidates]
    job_ids = [row["job_id"] for row in clean_jobs]
    candidate_required = ("candidate_id", "target_role", "location", "years_experience", "skills", "certifications", "resume_text")
    job_required = ("job_id", "title", "location", "required_experience_years", "required_skills", "mandatory_certifications", "description")
    candidate_missing = {key: sum(row.get(key) is None or row.get(key) == "" for row in clean_candidates) for key in candidate_required}
    job_missing = {key: sum(row.get(key) is None or row.get(key) == "" for row in clean_jobs) for key in job_required}
    negative_experience = sum(int(row["years_experience"]) < 0 for row in clean_candidates)
    negative_requirements = sum(int(row["required_experience_years"]) < 0 for row in clean_jobs)
    report = {
        "random_seed": random_seed,
        "candidates": {"rows": len(clean_candidates), "duplicate_ids": len(candidate_ids) - len(set(candidate_ids)), "missing_by_field": candidate_missing, "negative_experience_rows": negative_experience, "distinct_resume_texts": len({row["resume_text"] for row in clean_candidates}), "role_counts": dict(Counter(row["target_role"] for row in clean_candidates))},
        "jobs": {"rows": len(clean_jobs), "duplicate_ids": len(job_ids) - len(set(job_ids)), "missing_by_field": job_missing, "negative_experience_rows": negative_requirements, "role_counts": dict(Counter(row["title"] for row in clean_jobs)), "source": "BrighterMonday local JSON export" if imported_jobs else "synthetic"},
        "export_policy": "Latent label-generation fields are excluded; resume text is anonymized before export.",
    }
    invalid = (
        report["candidates"]["duplicate_ids"] or report["jobs"]["duplicate_ids"]
        or negative_experience or negative_requirements
        or any(candidate_missing.values()) or any(job_missing.values())
    )
    if invalid:
        raise ValueError("prepared dataset failed completeness, ID uniqueness, or non-negative experience checks")
    (export_dir / "data_quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not no_seed:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True)
        command = [sys.executable, str(PIPELINE / "seed_database.py"), "--candidates", str(candidates_count), "--jobs", str(len(clean_jobs)), "--data-dir", str(export_dir)]
        if imported_jobs:
            command.extend(["--jobs-file", str(imported_jobs)])
        if skip_graph:
            command.append("--skip-graph")
        run(command)
        if not skip_graph:
            run([sys.executable, str(PIPELINE / "load_esco_ontology.py")])
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=int, default=100)
    parser.add_argument("--jobs", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-seed", action="store_true", help="prepare files only")
    parser.add_argument("--skip-graph", action="store_true", help="skip candidate/job graph projection during database seeding")
    parser.add_argument("--brightermonday-export", type=Path, help="optional permitted local JSON export to use instead of synthetic jobs")
    parser.add_argument("--output-dir", type=Path, help="isolated destination for generated raw data, cleaned exports and quality report")
    args = parser.parse_args()
    report = prepare(args.candidates, args.jobs, args.seed, args.no_seed, args.skip_graph, args.brightermonday_export, args.output_dir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
