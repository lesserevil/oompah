"""Contract tests for the reusable historical workflow incident corpus."""

import hashlib
import json
from dataclasses import replace

import pytest

from oompah.workflow_contract import CANONICAL_STATUSES
from tests.fixtures_workflow_incidents import (
    CORPUS_VERSION,
    INCIDENTS,
    INCIDENTS_BY_ID,
    HistoricalFailure,
    detect_historical_failure,
    materialize_git,
    materialize_native_tracker,
    stable_corpus_json,
    validate_incident_scenario,
)

EXPECTED_INCIDENTS = {
    "OOMPAH-562",
    "OOMPAH-731",
    "OOMPAH-732",
    "OOMPAH-739",
    "OOMPAH-748",
    "OOMPAH-749",
    "OOMPAH-751",
}


def test_corpus_contains_every_systemic_incident_exactly_once():
    assert {scenario.source_task_id for scenario in INCIDENTS} == EXPECTED_INCIDENTS
    assert set(INCIDENTS_BY_ID) == EXPECTED_INCIDENTS
    assert len(INCIDENTS) == len(INCIDENTS_BY_ID)
    assert {scenario.corpus_version for scenario in INCIDENTS} == {CORPUS_VERSION}


@pytest.mark.parametrize("scenario", INCIDENTS, ids=lambda item: item.source_task_id)
def test_before_facts_deterministically_reproduce_historical_failure(scenario):
    assert detect_historical_failure(scenario) == scenario.historical_failure.code
    assert scenario.historical_failure.erroneous_effects
    assert validate_incident_scenario(scenario) == ()


@pytest.mark.parametrize("scenario", INCIDENTS, ids=lambda item: item.source_task_id)
def test_each_scenario_has_an_actionable_expected_decision(scenario):
    decision = scenario.expected
    assert decision.reason_code
    assert decision.disposition.value
    assert decision.owner.value
    assert decision.invariants
    assert scenario.after
    assert set(decision.status_updates.values()) <= set(CANONICAL_STATUSES)
    if "recovery" in decision.reason_code or decision.durable_jobs:
        assert decision.alert_severity not in {"warning", "critical"}


@pytest.mark.parametrize("scenario", INCIDENTS, ids=lambda item: item.source_task_id)
def test_scenarios_materialize_through_real_native_markdown_tracker(tmp_path, scenario):
    replay = materialize_native_tracker(tmp_path, scenario)

    for fixture in scenario.tasks:
        issue = replay.tracker.fetch_issue_detail(replay.identifiers[fixture.key])
        assert issue is not None
        assert issue.state == fixture.status
        if fixture.parent:
            assert issue.parent_id == replay.identifiers[fixture.parent]
        assert {blocker.identifier for blocker in issue.blocked_by} == {
            replay.identifiers[key] for key in fixture.finish_dependencies
        }
        assert {blocker.identifier for blocker in issue.start_blocked_by} == {
            replay.identifiers[key] for key in fixture.hard_start_dependencies
        }
        metadata = replay.tracker.get_metadata(issue.identifier)
        for field, expected in fixture.metadata.items():
            assert metadata[field] == expected

    task_files = list((tmp_path / "native" / ".oompah" / "tasks").glob("*/*.md"))
    assert len(task_files) == len(scenario.tasks)


@pytest.mark.parametrize(
    "scenario",
    [scenario for scenario in INCIDENTS if scenario.git is not None],
    ids=lambda item: item.source_task_id,
)
def test_git_incidents_replay_with_real_commit_ancestry_and_deleted_refs(
    tmp_path, scenario
):
    replay = materialize_git(tmp_path, scenario)
    assert scenario.git is not None

    for assertion in scenario.git.assertions:
        assert (
            replay.is_ancestor(assertion.ancestor, assertion.descendant)
            is assertion.expected
        )
    for ref in scenario.git.refs:
        assert replay.ref_exists(ref.name) is ref.present


@pytest.mark.parametrize(
    "scenario",
    [scenario for scenario in INCIDENTS if scenario.git is not None],
    ids=lambda item: item.source_task_id,
)
def test_git_incident_replay_is_deterministic(tmp_path, scenario):
    first = materialize_git(tmp_path / "first", scenario)
    second = materialize_git(tmp_path / "second", scenario)
    assert dict(first.commits) == dict(second.commits)


def test_corpus_serialization_is_stable_and_json_compatible():
    first = stable_corpus_json()
    second = stable_corpus_json()
    assert first == second
    assert json.loads(first)[0]["source_task_id"] == "OOMPAH-562"
    assert (
        hashlib.sha256(first.encode()).hexdigest()
        == hashlib.sha256(second.encode()).hexdigest()
    )


def test_validator_rejects_facts_that_no_longer_reproduce_declared_failure():
    scenario = INCIDENTS_BY_ID["OOMPAH-751"]
    changed = replace(
        scenario,
        before={**dict(scenario.before), "send_http_status": 403},
    )
    errors = validate_incident_scenario(changed)
    assert "before facts do not reproduce the declared historical failure" in errors


def test_validator_rejects_unversioned_failure_namespace():
    scenario = INCIDENTS_BY_ID["OOMPAH-562"]
    changed = replace(
        scenario,
        historical_failure=HistoricalFailure(
            "free_text_failure",
            scenario.historical_failure.summary,
            scenario.historical_failure.erroneous_status,
            scenario.historical_failure.erroneous_effects,
        ),
    )
    assert "historical failure code must use the historical namespace" in (
        validate_incident_scenario(changed)
    )
