import uuid
from collections import Counter

from data_pipeline.seed_recruiter_pipeline import BAD_SCORE, GREAT_SCORE, ROLES, fit_tier, job_id_for, pick_applicants

THRESHOLD = 0.46


def test_fit_tier_boundaries():
    assert fit_tier(GREAT_SCORE, THRESHOLD) == "great"
    assert fit_tier(GREAT_SCORE - 0.01, THRESHOLD) == "good"
    assert fit_tier(THRESHOLD, THRESHOLD) == "good"
    assert fit_tier(THRESHOLD - 0.01, THRESHOLD) == "mediocre"
    assert fit_tier(BAD_SCORE, THRESHOLD) == "mediocre"
    assert fit_tier(BAD_SCORE - 0.01, THRESHOLD) == "bad"


def _scores(values):
    return {uuid.uuid5(uuid.NAMESPACE_URL, str(index)): value for index, value in enumerate(values)}


def test_pick_applicants_caps_each_tier_and_is_repeatable():
    scores = _scores([0.9, 0.91, 0.92, 0.6, 0.3, 0.05, 0.04, 0.03])
    chosen = pick_applicants(scores, THRESHOLD, "job", Counter())
    assert chosen == pick_applicants(scores, THRESHOLD, "job", Counter())
    assert Counter(chosen.values()) == {"great": 2, "good": 1, "mediocre": 1, "bad": 2}
    assert all(fit_tier(scores[candidate_id], THRESHOLD) == tier for candidate_id, tier in chosen.items())


def test_pick_applicants_spreads_applications_across_candidates():
    scores = _scores([0.9, 0.91, 0.92, 0.93])
    used = Counter()
    first = pick_applicants(scores, THRESHOLD, "job", used)
    second = pick_applicants(scores, THRESHOLD, "job", used)
    assert not set(first) & set(second)


def test_roles_are_valid_and_job_ids_are_scoped_to_the_recruiter():
    assert len({role.key for role in ROLES}) == len(ROLES)
    for role in ROLES:
        assert role.salary_min <= role.salary_max and role.skills
        assert isinstance(role.certifications, tuple)
        # Applications are back-dated between posting and now, and the admin view flags postings at 14+ days as stale.
        assert 0 < role.posted_days < 14
    assert job_id_for("a@example.org", "qa") == job_id_for("A@example.org", "qa")
    assert job_id_for("a@example.org", "qa") != job_id_for("b@example.org", "qa")
