from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from oompah.work_decision import PermittedAction
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_facts import (
    FactDomain,
    FactObservation,
    WorkflowFacts,
)
from oompah.workflow_shadow import (
    MAX_DIAGNOSTIC_LIMIT,
    LegacyWorkflowProjection,
    ShadowComparisonState,
    WorkflowShadowEvaluator,
    normalize_workflow_engine_mode,
)


NOW = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


def facts(*, token: str | None = None) -> WorkflowFacts:
    values = {
        FactDomain.TASK: {
            "id": "issue-1",
            "identifier": "OOMPAH-1",
            "status": "Open",
            "issue_type": "task",
            "parent_id": None,
            "project_id": "project-a",
            "work_branch": "OOMPAH-1",
            "target_branch": "main",
            "assignment_id": None,
            "head_sha": None,
        },
        FactDomain.DEPENDENCIES: {"finish": [], "hard_start": []},
        FactDomain.CONTAINMENT: {"parent_id": None, "children": []},
        FactDomain.INTEGRATION: {"state": "none"},
        FactDomain.TERMINAL_AUDIT: {"phase": "none"},
        FactDomain.REVIEW_CI: {"ci": "none"},
        FactDomain.IMPLEMENTATION_AUTHORITY: {"lease_expires_at": None},
        FactDomain.RETRY_BUDGET: {"attempts": 0},
        FactDomain.LANDING: {"evidence_revisions": []},
        FactDomain.CONFIG: {"api_token": token} if token else {},
    }
    return WorkflowFacts(
        "project-a",
        "OOMPAH-1",
        NOW_ISO,
        {
            domain: FactObservation.known(
                domain,
                value,
                observed_at=NOW_ISO,
                source="test",
            )
            for domain, value in values.items()
        },
    )


def task() -> dict[str, object]:
    return {
        "project_id": "project-a",
        "identifier": "OOMPAH-1",
        "status": "Open",
        "issue_type": "task",
    }


def aligned_projection(consumer: str = "dispatch") -> LegacyWorkflowProjection:
    return LegacyWorkflowProjection(
        consumer,
        status="Open",
        disposition=TaskDisposition.RUNNABLE,
        owner=WorkflowOwner.DISPATCHER,
        reason_code="dispatch.eligible",
        permitted_actions=(PermittedAction.CLAIM_IMPLEMENTATION,),
    )


def divergent_projection(
    consumer: str = "dispatch",
) -> LegacyWorkflowProjection:
    return LegacyWorkflowProjection(
        consumer,
        status="Open",
        disposition=TaskDisposition.BLOCKED,
        owner=WorkflowOwner.OPERATOR,
        reason_code="legacy.no_owner",
        permitted_actions=(),
    )


def test_mode_validation_is_strict_and_normalized():
    assert normalize_workflow_engine_mode(" SHADOW ") == "shadow"
    assert normalize_workflow_engine_mode(None) == "off"
    with pytest.raises(ValueError, match="one of"):
        normalize_workflow_engine_mode("maybe")


def test_off_mode_has_zero_evaluation_side_effects():
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("evaluator must not run")

    shadow = WorkflowShadowEvaluator(mode="off", evaluator=forbidden)

    result = shadow.evaluate(
        task(), facts(), (aligned_projection(),), snapshot_generation=1, now=NOW
    )

    assert result.accepted is False
    assert calls == []
    assert shadow.summary()["tracked_task_count"] == 0


def test_aligned_comparison_records_reproducible_diagnostic():
    shadow = WorkflowShadowEvaluator(mode="shadow")

    result = shadow.evaluate(
        task(), facts(), (aligned_projection(),), snapshot_generation=7, now=NOW
    )

    assert result.accepted is True
    assert result.state is ShadowComparisonState.ALIGNED
    assert result.diagnostic["divergence"] is None
    assert result.diagnostic["decision"]["reason_code"] == "dispatch.eligible"
    assert result.diagnostic["facts_version"] == facts().facts_version
    assert shadow.summary()["divergence_count"] == 0


def test_divergence_is_structured_by_consumer_and_field():
    shadow = WorkflowShadowEvaluator(mode="shadow")

    result = shadow.evaluate(
        task(),
        facts(),
        (divergent_projection("dispatch"), aligned_projection("ui")),
        snapshot_generation=1,
        now=NOW,
    )

    divergence = result.diagnostic["divergence"]
    assert result.state is ShadowComparisonState.DIVERGED
    assert set(divergence["mismatches"]) == {"dispatch"}
    assert divergence["mismatches"]["dispatch"]["owner"] == {
        "legacy": "operator",
        "decision": "dispatcher",
    }
    assert shadow.summary()["divergences_by_consumer"] == {"dispatch": 1}


def test_same_semantic_divergence_is_deduplicated_across_generations():
    shadow = WorkflowShadowEvaluator(mode="shadow")

    first = shadow.evaluate(
        task(), facts(), (divergent_projection(),), snapshot_generation=1, now=NOW
    )
    second = shadow.evaluate(
        task(), facts(), (divergent_projection(),), snapshot_generation=2, now=NOW
    )

    first_divergence = first.diagnostic["divergence"]
    second_divergence = second.diagnostic["divergence"]
    assert second_divergence["fingerprint"] == first_divergence["fingerprint"]
    assert second_divergence["observation_count"] == 2
    assert shadow.summary()["divergence_count"] == 1


def test_alignment_clears_active_divergence_without_warning_history():
    shadow = WorkflowShadowEvaluator(mode="shadow")
    shadow.evaluate(
        task(), facts(), (divergent_projection(),), snapshot_generation=1, now=NOW
    )

    cleared = shadow.evaluate(
        task(), facts(), (aligned_projection(),), snapshot_generation=2, now=NOW
    )

    assert cleared.changed is True
    assert cleared.state is ShadowComparisonState.ALIGNED
    assert shadow.summary()["divergence_count"] == 0
    assert shadow.summary()["resolved_count"] == 1


def test_stale_snapshot_generation_cannot_overwrite_newer_diagnostic():
    shadow = WorkflowShadowEvaluator(mode="shadow")
    newest = shadow.evaluate(
        task(), facts(), (aligned_projection(),), snapshot_generation=5, now=NOW
    )

    stale = shadow.evaluate(
        task(), facts(), (divergent_projection(),), snapshot_generation=4, now=NOW
    )

    assert stale.accepted is False
    assert stale.reason == "stale snapshot generation rejected"
    assert stale.diagnostic == newest.diagnostic
    assert shadow.summary()["stale_rejected_count"] == 1


def test_listener_runs_only_for_semantic_change():
    shadow = WorkflowShadowEvaluator(mode="shadow")
    summaries = []
    shadow.add_listener(lambda summary: summaries.append(dict(summary)))

    shadow.evaluate(
        task(), facts(), (divergent_projection(),), snapshot_generation=1, now=NOW
    )
    shadow.evaluate(
        task(), facts(), (divergent_projection(),), snapshot_generation=2, now=NOW
    )
    shadow.evaluate(
        task(), facts(), (aligned_projection(),), snapshot_generation=3, now=NOW
    )

    assert len(summaries) == 2
    assert summaries[0]["divergence_count"] == 1
    assert summaries[1]["divergence_count"] == 0


def test_diagnostics_are_secret_redacted_before_storage():
    secret = "ghp_0123456789abcdefghijklmnopqrstuvwxyz"  # pragma: allowlist secret
    shadow = WorkflowShadowEvaluator(mode="shadow")

    result = shadow.evaluate(
        task(),
        facts(token=secret),
        (aligned_projection(),),
        snapshot_generation=1,
        now=NOW,
    )
    encoded = json.dumps(result.diagnostic)

    assert secret not in encoded
    assert "[REDACTED]" in encoded


def test_diagnostic_size_is_fail_closed_and_bounded():
    shadow = WorkflowShadowEvaluator(mode="shadow", max_diagnostic_bytes=1024)
    large = facts(token="x" * 20_000)

    result = shadow.evaluate(
        task(), large, (aligned_projection(),), snapshot_generation=1, now=NOW
    )

    assert result.diagnostic["truncated"] is True
    assert len(json.dumps(result.diagnostic).encode()) < 1024


def test_projection_can_assert_only_the_field_a_consumer_owns():
    shadow = WorkflowShadowEvaluator(mode="shadow")
    ui = LegacyWorkflowProjection("ui", status="Open")

    result = shadow.evaluate(task(), facts(), (ui,), snapshot_generation=1, now=NOW)

    assert result.state is ShadowComparisonState.ALIGNED


def test_project_filter_and_scan_bounds_are_enforced():
    shadow = WorkflowShadowEvaluator(mode="shadow")
    shadow.evaluate(
        task(), facts(), (aligned_projection(),), snapshot_generation=1, now=NOW
    )

    assert len(shadow.diagnostics(project_id="project-a")) == 1
    assert shadow.diagnostics(project_id="project-b") == ()
    with pytest.raises(ValueError, match="between"):
        shadow.diagnostics(limit=MAX_DIAGNOSTIC_LIMIT + 1)


def test_mode_reload_preserves_diagnostics_but_stops_evaluation():
    shadow = WorkflowShadowEvaluator(mode="shadow")
    shadow.evaluate(
        task(), facts(), (aligned_projection(),), snapshot_generation=1, now=NOW
    )

    shadow.set_mode("off")
    stopped = shadow.evaluate(
        task(),
        facts(),
        (divergent_projection(),),
        snapshot_generation=2,
        now=NOW,
    )

    assert stopped.accepted is False
    assert shadow.diagnostic("project-a", "OOMPAH-1")["state"] == "aligned"
    assert shadow.summary()["mode"] == "off"


def test_evaluation_does_not_mutate_task_facts_or_projection():
    shadow = WorkflowShadowEvaluator(mode="shadow")
    task_value = task()
    fact_value = facts()
    projection = divergent_projection()
    original_task = dict(task_value)
    original_facts = fact_value.stable_json()
    original_projection = projection.to_dict()

    shadow.evaluate(
        task_value,
        fact_value,
        (projection,),
        snapshot_generation=1,
        now=NOW,
    )

    assert task_value == original_task
    assert fact_value.stable_json() == original_facts
    assert projection.to_dict() == original_projection


def test_returned_diagnostics_cannot_mutate_registry_state():
    shadow = WorkflowShadowEvaluator(mode="shadow")
    shadow.evaluate(
        task(),
        facts(),
        (LegacyWorkflowProjection("dispatch", status="Backlog"),),
        snapshot_generation=1,
        now=NOW,
    )

    diagnostic = shadow.diagnostic("project-a", "OOMPAH-1")
    diagnostic["decision"]["status"] = "Archived"
    listed = shadow.diagnostics()
    listed[0]["legacy"][0]["status"] = "Archived"

    stored = shadow.diagnostic("project-a", "OOMPAH-1")
    assert stored["decision"]["status"] == "Open"
    assert stored["legacy"][0]["status"] == "Backlog"
