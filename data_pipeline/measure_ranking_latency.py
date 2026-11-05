"""Time the ranking step of "Evaluate candidates" on this machine, for the latency figure on the landing page.

Runs the same eligibility filter, encoding and scoring as POST /matches/evaluate/{job_id}, but saves nothing. A first
pass loads the model and is excluded. "encoding" clears the embedding cache each run (the first evaluation after a
restart or a new resume); "cached" keeps it (a repeat evaluation). This process does its own work beside the live API.

    python data_pipeline/measure_ranking_latency.py --runs 7
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path
from time import perf_counter

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.matches import _candidate_rule_result, _score_candidate  # noqa: E402
from app.core.hybrid_matcher import _embedding_cache, semantic_similarities  # noqa: E402
from app.db.models import Candidate, JobPosting, JobStatus, User  # noqa: E402
from app.db.postgres import SessionLocal  # noqa: E402


def rank_once(candidates: list[Candidate], job: JobPosting) -> int:
    eligible = [candidate for candidate in candidates if _candidate_rule_result(candidate, job).passed]
    scores = semantic_similarities([candidate.parsed_resume_text or "" for candidate in eligible], job.description) if eligible else []
    by_candidate = {candidate.candidate_id: score for candidate, score in zip(eligible, scores)}
    sorted((_score_candidate(candidate, job, by_candidate.get(candidate.candidate_id)) for candidate in candidates), key=lambda result: -result.final_score)
    return len(eligible)


def summarise(label: str, seconds: list[float]) -> str:
    return f"{label}: median {statistics.median(seconds):.2f} s (min {min(seconds):.2f}, max {max(seconds):.2f}, {len(seconds)} runs)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=7)
    args = parser.parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    with SessionLocal() as db:
        # Read-only: the session is never committed, and remote jobs make the largest eligible pool to rank.
        candidates = list(db.scalars(select(Candidate).join(User, Candidate.user_id == User.user_id).where(User.is_active.is_(True))))
        jobs = list(db.scalars(select(JobPosting).where(JobPosting.status == JobStatus.open)))
        if not candidates or not jobs:
            raise SystemExit("Needs at least one active candidate and one open job")
        job = max(jobs, key=lambda posting: (sum(_candidate_rule_result(candidate, posting).passed for candidate in candidates), str(posting.job_id)))
        started = perf_counter()
        eligible = rank_once(candidates, job)
        print(f"Model load and first pass, excluded: {perf_counter() - started:.1f} s")
        print(f"Ranking {len(candidates)} candidates, {eligible} eligible, for one role")
        encoding, cached = [], []
        for _ in range(args.runs):
            _embedding_cache.clear()
            started = perf_counter()
            rank_once(candidates, job)
            encoding.append(perf_counter() - started)
        for _ in range(args.runs):
            started = perf_counter()
            rank_once(candidates, job)
            cached.append(perf_counter() - started)
        db.rollback()
    print(summarise("encoding", encoding))
    print(summarise("cached", cached))


if __name__ == "__main__":
    main()
