from collections import Counter

import pytest

from app.db.graph_repair import _merge_into, choose_canonical, ontology_names


def test_ontology_spelling_wins():
    assert choose_canonical(["aws", "Aws"], ["AWS"], Counter({"aws": 50})) == "AWS"


def test_most_used_postgres_spelling_wins_without_an_ontology_name():
    assert choose_canonical(["active directory"], [], Counter({"Active Directory": 8, "active directory": 1})) == "Active Directory"


def test_capitals_break_a_tie_and_unknown_names_stay_as_they_are():
    assert choose_canonical(["incident response", "Incident Response"], [], Counter()) == "Incident Response"
    assert choose_canonical(["menu planning"], [], Counter()) == "menu planning"


def test_names_are_not_trimmed_into_a_wrong_group():
    assert choose_canonical([" SQL "], ["SQL"], Counter()) == "SQL"
    assert choose_canonical(["Java"], ["JavaScript"], Counter()) == "Java"


def test_ontology_file_includes_related_names():
    names = ontology_names()
    assert "Python" in names and len(names) > 50


class _Result:
    def __init__(self, kinds=()):
        self.kinds = kinds

    def value(self):
        return list(self.kinds)

    def consume(self):
        return None


class _Transaction:
    def __init__(self, kinds):
        self.kinds = kinds
        self.queries = []

    def run(self, query, **_):
        self.queries.append(query)
        return _Result(self.kinds if "RETURN DISTINCT" in query else ())


def test_merge_moves_both_directions_before_deleting():
    transaction = _Transaction(["RELATED_TO"])
    _merge_into(transaction, "Skill", "AWS", "aws")
    moves = [query for query in transaction.queries if "MERGE" in query]
    assert any("(other)-[moved:RELATED_TO]->(target)" in query for query in moves)
    assert any("(target)-[moved:RELATED_TO]->(other)" in query for query in moves)
    assert all("other <> target" in query for query in moves)
    assert "DETACH DELETE" in transaction.queries[-1]


def test_merge_refuses_an_unexpected_relationship_type():
    with pytest.raises(ValueError):
        _merge_into(_Transaction(["BAD`TYPE"]), "Skill", "AWS", "aws")
