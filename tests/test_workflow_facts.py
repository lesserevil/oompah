"""Versioning, scope, and landing-proof coverage for WorkflowFacts."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from oompah.models import BlockerRef, Issue
from oompah.workflow_facts import (
    CollectedValue,
    FactDomain,
    FactObservation,
    FactState,
    GitLandingCollector,
    LandingFact,
    LandingProofKind,
    LandingRequest,
    LandingState,
    REQUIRED_FACT_DOMAINS,
    WorkflowFactCollector,
    WorkflowFacts,
)
from tests.fixtures_workflow_incidents import INCIDENTS_BY_ID, materialize_git

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


class FakeTracker:
    def __init__(self, issue: Issue | None, children=()):
        self.issue = issue
        self.children = list(children)
        self.fetch_error: Exception | None = None
        self.children_error: Exception | None = None

    def fetch_issue_detail(self, identifier):
        if self.fetch_error:
            raise self.fetch_error
        if self.issue and identifier == self.issue.identifier:
            return self.issue
        return None

    def fetch_children(self, identifier):
        if self.children_error:
            raise self.children_error
        return list(self.children)


def _issue(**overrides):
    values = {
        "id": "TASK-1",
        "identifier": "TASK-1",
        "title": "Facts",
        "state": "Ready to Integrate",
        "project_id": "project-1",
        "issue_type": "task",
        "parent_id": "EPIC-1",
        "work_branch": "task-1",
        "target_branch": "epic-1",
        "assignment_id": "generation-1",
        "head_sha": "a" * 40,
        "blocked_by": [BlockerRef(identifier="TASK-0", state="Done")],
        "start_blocked_by": [BlockerRef(identifier="TASK-X", state="Open")],
    }
    values.update(overrides)
    return Issue(**values)


def _all_observations(at=NOW_ISO):
    return {
        domain: FactObservation.known(
            domain,
            {"domain": domain.value},
            observed_at=at,
            source="test",
        )
        for domain in REQUIRED_FACT_DOMAINS
    }


def _git(repo, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": __import__("os").environ["PATH"],
            "GIT_AUTHOR_NAME": "Facts",
            "GIT_AUTHOR_EMAIL": "facts@example.invalid",
            "GIT_COMMITTER_NAME": "Facts",
            "GIT_COMMITTER_EMAIL": "facts@example.invalid",
        },
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "commit", "--allow-empty", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-b", "task")
    _git(repo, "commit", "--allow-empty", "-m", "task")
    task = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "main")
    return repo, base, task


def test_fact_observation_revision_ignores_observation_time_and_freezes_values():
    first = FactObservation.known(
        FactDomain.REVIEW_CI,
        {"checks": ["test", "lint"]},
        observed_at=NOW_ISO,
        source="forge",
    )
    later = FactObservation.known(
        FactDomain.REVIEW_CI,
        {"checks": ["test", "lint"]},
        observed_at=(NOW + timedelta(minutes=1)).isoformat(),
        source="forge",
    )

    assert first.revision == later.revision
    assert first.value["checks"] == ("test", "lint")
    with pytest.raises(TypeError):
        first.value["checks"] = ()


def test_missing_stale_and_error_are_distinct_semantic_facts():
    missing = FactObservation.missing(
        FactDomain.REVIEW_CI, observed_at=NOW_ISO, source="forge"
    )
    stale = FactObservation.stale(
        FactDomain.REVIEW_CI,
        {"state": "open"},
        observed_at=NOW_ISO,
        source="forge",
    )
    error = FactObservation.error(
        FactDomain.REVIEW_CI,
        observed_at=NOW_ISO,
        source="forge",
        error_code="forge_timeout",
    )

    assert {missing.state, stale.state, error.state} == {
        FactState.MISSING,
        FactState.STALE,
        FactState.ERROR,
    }
    assert len({missing.revision, stale.revision, error.revision}) == 3


@pytest.mark.parametrize(
    "factory",
    [
        lambda: FactObservation(
            FactDomain.CONFIG,
            FactState.MISSING,
            {"unexpected": True},
            NOW_ISO,
            "test",
        ),
        lambda: FactObservation(
            FactDomain.CONFIG,
            FactState.ERROR,
            None,
            NOW_ISO,
            "test",
        ),
        lambda: FactObservation(
            FactDomain.CONFIG,
            FactState.KNOWN,
            {},
            NOW_ISO,
            "test",
            error_code="wrong",
        ),
        lambda: FactObservation(
            FactDomain.CONFIG,
            FactState.KNOWN,
            None,
            NOW_ISO,
            "test",
        ),
    ],
)
def test_fact_observation_rejects_ambiguous_shapes(factory):
    with pytest.raises(ValueError):
        factory()


def test_workflow_facts_version_is_deterministic_and_time_independent():
    first = WorkflowFacts("project-1", "TASK-1", NOW_ISO, _all_observations())
    later_time = (NOW + timedelta(hours=1)).isoformat()
    second = WorkflowFacts(
        "project-1",
        "TASK-1",
        later_time,
        _all_observations(later_time),
    )

    assert first.facts_version == second.facts_version
    assert WorkflowFacts.from_dict(first.to_dict()) == first
    assert WorkflowFacts.from_dict(first.to_dict()).stable_json() == first.stable_json()


def test_workflow_facts_requires_every_domain_exactly_once():
    observations = _all_observations()
    observations.pop(FactDomain.RETRY_BUDGET)
    with pytest.raises(ValueError, match="domains mismatch"):
        WorkflowFacts("project-1", "TASK-1", NOW_ISO, observations)


def test_landing_fact_positive_negative_unknown_and_revision_semantics():
    positive = LandingFact(
        "task",
        "main",
        "a" * 40,
        {"kind": LandingProofKind.MERGE_COMMIT.value, "merge_sha": "b" * 40},
        NOW_ISO,
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )
    later = replace(positive, observed_at=(NOW + timedelta(hours=1)).isoformat())
    negative = LandingFact(
        "task",
        "main",
        "a" * 40,
        {"kind": LandingProofKind.NOT_ANCESTOR.value},
        NOW_ISO,
        "project-1",
        state=LandingState.NOT_LANDED,
    )
    unknown = LandingFact(
        "task",
        "main",
        "a" * 40,
        {"kind": LandingProofKind.SOURCE_UNAVAILABLE.value},
        NOW_ISO,
        "project-1",
        state=LandingState.UNKNOWN,
        error_code="git_observation_failed",
    )

    assert positive.evidence_revision == later.evidence_revision
    assert (
        len(
            {
                positive.evidence_revision,
                negative.evidence_revision,
                unknown.evidence_revision,
            }
        )
        == 3
    )
    assert LandingFact.from_dict(positive.to_dict()) == positive


def test_nonpositive_landing_evidence_cannot_claim_durability():
    with pytest.raises(ValueError, match="positive"):
        LandingFact(
            "task",
            "main",
            None,
            {"kind": "unobserved"},
            NOW_ISO,
            "project-1",
            state=LandingState.UNKNOWN,
            durable=True,
        )


@pytest.mark.parametrize(
    "request_factory",
    [
        lambda: LandingRequest("--help", "main"),
        lambda: LandingRequest("task\nother", "main"),
        lambda: LandingRequest("task", "main", "not-a-sha"),
    ],
)
def test_landing_request_rejects_unsafe_git_arguments(request_factory):
    with pytest.raises(ValueError):
        request_factory()


def test_git_landing_collector_distinguishes_positive_negative_and_unknown(tmp_path):
    repo, base, task = _git_repo(tmp_path)
    collector = GitLandingCollector(repo, project_id="project-1", clock=lambda: NOW)

    negative = collector.collect(LandingRequest("task", "main", task))
    _git(repo, "merge", "--no-ff", "task", "-m", "merge")
    positive = collector.collect(LandingRequest("task", "main", task))
    unknown = collector.collect(LandingRequest("deleted", "main"))

    assert negative.state is LandingState.NOT_LANDED
    assert negative.proof["target_sha"] == base
    assert positive.state is LandingState.LANDED
    assert positive.durable is True
    assert unknown.state is LandingState.UNKNOWN
    assert unknown.proof["kind"] == LandingProofKind.SOURCE_UNAVAILABLE.value


def test_deleted_source_branch_remains_provable_from_exact_revision(tmp_path):
    repo, _, task = _git_repo(tmp_path)
    _git(repo, "merge", "--no-ff", "task", "-m", "merge")
    _git(repo, "branch", "-D", "task")

    fact = GitLandingCollector(repo, project_id="project-1", clock=lambda: NOW).collect(
        LandingRequest("task", "main", task)
    )

    assert fact.state is LandingState.LANDED
    assert fact.revision == task
    assert fact.proof["kind"] == LandingProofKind.GIT_ANCESTRY.value


def test_durable_prior_survives_unavailable_source_object(tmp_path):
    repo, _, _ = _git_repo(tmp_path)
    collector = GitLandingCollector(repo, project_id="project-1", clock=lambda: NOW)
    prior = LandingFact(
        "deleted-task",
        "main",
        "f" * 40,
        {"kind": LandingProofKind.TERMINAL_AUDIT.value, "audit_id": "audit-1"},
        NOW_ISO,
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )

    preserved = collector.collect(
        LandingRequest("deleted-task", "main", "f" * 40, prior=prior)
    )
    cross_project = GitLandingCollector(
        repo, project_id="project-2", clock=lambda: NOW
    ).collect(LandingRequest("deleted-task", "main", "f" * 40, prior=prior))

    assert preserved.state is LandingState.LANDED
    assert preserved.evidence_revision == prior.evidence_revision
    assert cross_project.state is LandingState.UNKNOWN


def test_durable_prior_survives_later_target_rewrite(tmp_path):
    repo, base, task = _git_repo(tmp_path)
    _git(repo, "merge", "--no-ff", "task", "-m", "merge")
    collector = GitLandingCollector(repo, project_id="project-1", clock=lambda: NOW)
    prior = collector.collect(LandingRequest("task", "main", task))
    _git(repo, "reset", "--hard", base)

    current_only = collector.collect(LandingRequest("task", "main", task))
    preserved = collector.collect(LandingRequest("task", "main", task, prior=prior))

    assert current_only.state is LandingState.NOT_LANDED
    assert preserved.state is LandingState.LANDED
    assert preserved.evidence_revision == prior.evidence_revision


def test_git_observation_failure_becomes_unknown_fact(tmp_path):
    missing_repo = tmp_path / "does-not-exist"

    fact = GitLandingCollector(
        missing_repo, project_id="project-1", clock=lambda: NOW
    ).collect(LandingRequest("task", "main"))

    assert fact.state is LandingState.UNKNOWN
    assert fact.error_code == "git_repository_unavailable"


def test_workflow_facts_rejects_cross_project_landing():
    landing = LandingFact(
        "task",
        "main",
        "a" * 40,
        {"kind": LandingProofKind.TERMINAL_AUDIT.value},
        NOW_ISO,
        "project-2",
        state=LandingState.LANDED,
        durable=True,
    )
    observations = _all_observations()
    observations[FactDomain.LANDING] = FactObservation.known(
        FactDomain.LANDING,
        {"evidence_revisions": [landing.evidence_revision]},
        observed_at=NOW_ISO,
        source="test",
    )

    with pytest.raises(ValueError, match="WorkflowFacts project"):
        WorkflowFacts("project-1", "TASK-1", NOW_ISO, observations, landings=(landing,))


def test_nested_landing_is_evaluated_on_immediate_target(tmp_path):
    repo, _, task = _git_repo(tmp_path)
    _git(repo, "branch", "epic-parent", "task")
    collector = GitLandingCollector(repo, project_id="project-1", clock=lambda: NOW)

    immediate = collector.collect(LandingRequest("task", "epic-parent", task))
    root = collector.collect(LandingRequest("task", "main", task))

    assert immediate.state is LandingState.LANDED
    assert root.state is LandingState.NOT_LANDED


def test_collector_normalizes_task_graph_and_explicit_missing_domains():
    issue = _issue()
    child = _issue(
        id="TASK-2",
        identifier="TASK-2",
        parent_id="TASK-1",
        state="Open",
        issue_type="feature",
    )
    collector = WorkflowFactCollector(
        project_id="project-1",
        tracker=FakeTracker(issue, [child]),
        clock=lambda: NOW,
    )

    facts = collector.collect("TASK-1")

    assert facts.fact(FactDomain.TASK).value["status"] == "Ready to Integrate"
    assert (
        facts.fact(FactDomain.DEPENDENCIES).value["finish"][0]["identifier"] == "TASK-0"
    )
    assert (
        facts.fact(FactDomain.CONTAINMENT).value["children"][0]["identifier"]
        == "TASK-2"
    )
    for domain in WorkflowFactCollector._EXTERNAL_DOMAINS:
        assert facts.fact(domain).state is FactState.MISSING
    assert facts.fact(FactDomain.LANDING).state is FactState.MISSING


def test_task_graph_order_does_not_change_facts_version():
    first_issue = _issue(
        blocked_by=[
            BlockerRef(identifier="TASK-B", state="Open"),
            BlockerRef(identifier="TASK-A", state="Done"),
        ]
    )
    second_issue = replace(
        first_issue, blocked_by=list(reversed(first_issue.blocked_by))
    )
    children = [
        _issue(id="TASK-3", identifier="TASK-3", parent_id="TASK-1"),
        _issue(id="TASK-2", identifier="TASK-2", parent_id="TASK-1"),
    ]
    first = WorkflowFactCollector(
        project_id="project-1",
        tracker=FakeTracker(first_issue, children),
        clock=lambda: NOW,
    ).collect("TASK-1")
    second = WorkflowFactCollector(
        project_id="project-1",
        tracker=FakeTracker(second_issue, list(reversed(children))),
        clock=lambda: NOW,
    ).collect("TASK-1")

    assert first.facts_version == second.facts_version


def test_collector_preserves_source_errors_without_false_empty_values():
    def fail(_issue):
        raise TimeoutError("secret transport detail")

    collector = WorkflowFactCollector(
        project_id="project-1",
        tracker=FakeTracker(_issue()),
        sources={FactDomain.REVIEW_CI: fail},
        clock=lambda: NOW,
    )

    fact = collector.collect("TASK-1").fact(FactDomain.REVIEW_CI)

    assert fact.state is FactState.ERROR
    assert fact.value is None
    assert fact.error_code == "review_ci_timeouterror"
    assert "secret" not in fact.to_dict().values()


def test_collector_marks_expired_provider_values_stale():
    collector = WorkflowFactCollector(
        project_id="project-1",
        tracker=FakeTracker(_issue()),
        sources={
            FactDomain.RETRY_BUDGET: lambda _issue: CollectedValue(
                {"remaining": 2},
                (NOW - timedelta(minutes=10)).isoformat(),
                "job-store",
                stale_after_seconds=60,
            )
        },
        clock=lambda: NOW,
    )

    fact = collector.collect("TASK-1").fact(FactDomain.RETRY_BUDGET)

    assert fact.state is FactState.STALE
    assert fact.value["remaining"] == 2


@pytest.mark.parametrize(
    ("issue", "error_code", "state"),
    [
        (None, None, FactState.MISSING),
        (_issue(project_id="project-2"), "project_scope_mismatch", FactState.ERROR),
    ],
)
def test_collector_fails_closed_for_missing_or_cross_project_task(
    issue, error_code, state
):
    facts = WorkflowFactCollector(
        project_id="project-1",
        tracker=FakeTracker(issue),
        clock=lambda: NOW,
    ).collect("TASK-1")

    assert all(fact.state is state for fact in facts.observations.values())
    if error_code:
        assert all(
            fact.error_code == error_code for fact in facts.observations.values()
        )


def test_tracker_failure_is_explicit_in_every_domain():
    tracker = FakeTracker(_issue())
    tracker.fetch_error = ConnectionError("offline")
    facts = WorkflowFactCollector(
        project_id="project-1", tracker=tracker, clock=lambda: NOW
    ).collect("TASK-1")

    assert all(fact.state is FactState.ERROR for fact in facts.observations.values())
    assert all(
        fact.error_code == "tracker_connectionerror"
        for fact in facts.observations.values()
    )


def test_landing_requests_require_collector_instead_of_becoming_negative():
    facts = WorkflowFactCollector(
        project_id="project-1",
        tracker=FakeTracker(_issue()),
        clock=lambda: NOW,
    ).collect("TASK-1", landing_requests=[LandingRequest("task", "main")])

    assert facts.fact(FactDomain.LANDING).state is FactState.ERROR
    assert facts.fact(FactDomain.LANDING).error_code == "landing_collector_unavailable"
    assert facts.landings == ()


def test_fact_collector_rejects_cross_project_landing_collector(tmp_path):
    repo, _, _ = _git_repo(tmp_path)
    with pytest.raises(ValueError, match="project"):
        WorkflowFactCollector(
            project_id="project-1",
            tracker=FakeTracker(_issue()),
            landing_collector=GitLandingCollector(repo, project_id="project-2"),
            clock=lambda: NOW,
        )


def test_landing_collector_failure_is_an_explicit_error_fact():
    class BrokenLandingCollector:
        project_id = "project-1"

        def collect(self, request):
            raise TimeoutError("transport detail")

    facts = WorkflowFactCollector(
        project_id="project-1",
        tracker=FakeTracker(_issue()),
        landing_collector=BrokenLandingCollector(),
        clock=lambda: NOW,
    ).collect("TASK-1", landing_requests=[LandingRequest("task", "main")])

    assert facts.fact(FactDomain.LANDING).state is FactState.ERROR
    assert facts.fact(FactDomain.LANDING).error_code == "landing_timeouterror"
    assert facts.landings == ()


def test_collector_composes_first_class_landings_into_facts_version(tmp_path):
    repo, _, task = _git_repo(tmp_path)
    _git(repo, "merge", "--no-ff", "task", "-m", "merge")
    collector = WorkflowFactCollector(
        project_id="project-1",
        tracker=FakeTracker(_issue()),
        landing_collector=GitLandingCollector(
            repo, project_id="project-1", clock=lambda: NOW
        ),
        clock=lambda: NOW,
    )

    facts = collector.collect(
        "TASK-1", landing_requests=[LandingRequest("task", "main", task)]
    )

    assert facts.landings[0].state is LandingState.LANDED
    assert facts.fact(FactDomain.LANDING).value["evidence_revisions"] == (
        facts.landings[0].evidence_revision,
    )
    assert WorkflowFacts.from_dict(facts.to_dict()) == facts


@pytest.mark.parametrize(
    ("incident_id", "source_key", "target_ref"),
    [
        ("OOMPAH-739", "child-head", "main"),
        ("OOMPAH-748", "child-head", "epic-parent"),
    ],
)
def test_historical_deleted_and_nested_landing_incidents_replay_as_positive(
    tmp_path, incident_id, source_key, target_ref
):
    scenario = INCIDENTS_BY_ID[incident_id]
    replay = materialize_git(tmp_path / incident_id, scenario)

    fact = GitLandingCollector(
        replay.path, project_id="project-1", clock=lambda: NOW
    ).collect(LandingRequest("deleted-source", target_ref, replay.commits[source_key]))

    assert fact.state is LandingState.LANDED
    assert fact.durable is True
    assert fact.target == target_ref
