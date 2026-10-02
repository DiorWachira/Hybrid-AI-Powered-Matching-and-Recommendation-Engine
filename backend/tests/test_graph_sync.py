from unittest.mock import MagicMock

import pytest

from app.db.graph_sync import _project, ensure_graph_schema, sync_graph_events


def test_graph_schema_has_unique_candidate_and_job_ids():
    driver = MagicMock()
    ensure_graph_schema(driver)
    statements = [call.args[0] for call in driver.session.return_value.__enter__.return_value.run.call_args_list]
    assert any("node:Candidate" in query and "node.id IS UNIQUE" in query for query in statements)
    assert any("node:Job" in query and "node.id IS UNIQUE" in query for query in statements)


def test_job_projection_uses_id_and_replaces_edges():
    transaction = MagicMock()
    transaction.run.return_value.single.return_value = None
    _project(transaction, "job", "job-one", {"skills": [" SQL ", "sql"], "certifications": [], "title": "Analyst", "status": "open", "industry": "Finance"})
    calls = transaction.run.call_args_list
    assert any("node:Job {id: $id}" in call.args[0] for call in calls)
    assert any("edge:REQUIRES_SKILL" in call.args[0] and "DELETE edge" in call.args[0] for call in calls)
    skill_writes = [call for call in calls if "MERGE (target:Skill" in call.args[0]]
    assert len(skill_writes) == 1
    assert skill_writes[0].kwargs["name"] == "sql"
    assert any("BELONGS_TO" in call.args[0] for call in calls)


def test_graph_failure_does_not_acknowledge_outbox_event():
    database = MagicMock()
    event = MagicMock(entity_type="candidate")
    database.scalar.side_effect = [True, event]
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value.execute_write.side_effect = RuntimeError("graph unavailable")
    with pytest.raises(RuntimeError, match="graph unavailable"):
        sync_graph_events(database, driver)
    database.delete.assert_not_called()
    assert database.begin.return_value.__exit__.call_args.args[0] is RuntimeError


def test_deleted_application_removes_only_its_edge():
    transaction = MagicMock()
    _project(transaction, "application", "application-one", None)
    transaction.run.assert_called_once_with("MATCH ()-[edge:APPLIED_TO {application_id: $id}]->() DELETE edge", id="application-one")