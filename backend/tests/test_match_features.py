import pytest

from app.core.match_features import growth_score, skill_overlap


@pytest.mark.parametrize("candidate,required,expected", [
    (["SQL", "sql", "Excel"], ["sql", "Python"], 0.5),
    (["Python"], ["Data Analysis"], 0.0),
    (["SQL"], [], 0.0),
    ([], ["SQL"], 0.0),
])
def test_direct_skill_contract(candidate, required, expected):
    assert skill_overlap(candidate, required) == expected


@pytest.mark.parametrize("years,required,certificates", [(0, 0, 0), (1, 0, 1), (2, 4, 1), (10, 2, 4)])
def test_growth_preserves_serving_formula(years, required, certificates):
    assert growth_score(years, required, certificates) == (min(years / max(required, 1), 1.0) + min(certificates / 2, 1.0)) / 2