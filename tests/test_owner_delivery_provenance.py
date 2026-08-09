"""Regression coverage for revision-bound project-owner delivery facts."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from oompah.integration import IntegrationRecord
from oompah.integration_workflow import (
    IntegrationLandingRequestResolver,
    IntegrationWorkflowController,
)
from oompah.models import Issue
from oompah.owner_delivery_provenance import collect_owner_delivery_provenance
from oompah.terminal_audit import (
    ContributorIdentity,
    EvidenceFingerprint,
    OverrideRecord,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import TerminalAuditMetadata
from oompah.workflow_fact_model import FactDomain, LandingRequest, LandingState
from oompah.workflow_facts import WorkflowFactCollector
from oompah.workflow_jobs import WorkflowJobStore

PROJECT_ID = "project-1"
TASK_ID = "TASK-1"
HEAD = "a" * 40
OLDER_HEAD = "b" * 40
NOW = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


class Tracker:
    def __init__(self, issue: Issue):
        self.issue = issue

    def fetch_issue_detail(self, identifier):
        return self.issue if identifier == self.issue.identifier else None

    def fetch_children(self, _identifier):
        return []


class ForbiddenLandingCollector:
    project_id = PROJECT_ID

    def collect_many(self, _requests):
        raise AssertionError("owner-authorized delivery must precede Git refresh")


def issue(*, head: str = HEAD, target: str = "main") -> Issue:
    return Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="Owner delivery",
        state="Done",
        project_id=PROJECT_ID,
        issue_type="task",
        work_branch=TASK_ID,
        target_branch=target,
        integration=IntegrationRecord(
            state="ready",
            task_branch=TASK_ID,
            base_branch=target,
            head_sha=head,
        ),
    )


def project(owner: str = "owner"):
    return SimpleNamespace(
        status_actor_login=owner,
        tracker_owner=None,
        status_label_authorized_logins=[],
    )


def override(
    *,
    selected_sha: str | None = HEAD,
    actor: str = "owner",
    fingerprint: EvidenceFingerprint | None = None,
) -> dict:
    fingerprint = fingerprint or compute_issue_evidence_fingerprint(issue(), PROJECT_ID)
    record = OverrideRecord(
        override_id=f"override-{selected_sha or 'unbound'}",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        authorized_by=ContributorIdentity(actor, "api"),
        reason="Exact owner delivery.",
        created_at=NOW.isoformat(),
        selected_ref=(TASK_ID if selected_sha is not None else None),
        selected_sha=selected_sha,
    ).to_dict()
    record["applied"] = True
    return record


def metadata(*records: dict, audits=()) -> TerminalAuditMetadata:
    return TerminalAuditMetadata(
        pending_chain=list(audits),
        unknown_fields={"oompah.terminal_override_records": list(records)},
    )


def provenance(current: Issue, document: TerminalAuditMetadata):
    return collect_owner_delivery_provenance(
        current,
        document,
        project_id=PROJECT_ID,
        project=project(),
    )


def test_bound_authorized_override_projects_exact_delivery() -> None:
    result = provenance(issue(), metadata(override()))

    assert result is not None
    assert (result.source, result.target, result.revision) == (
        TASK_ID,
        "main",
        HEAD,
    )
    assert result.selected_ref == TASK_ID
    assert result.authorized_by == "owner"


def test_legacy_override_can_reuse_matching_bound_audit() -> None:
    raw = override(selected_sha=None)
    fingerprint = EvidenceFingerprint.from_dict(raw["evidence_fingerprint"])
    audit = TerminalAuditRecord(
        audit_id="audit-bound",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.CANCELLED,
        selected_ref=TASK_ID,
        selected_sha=HEAD,
    )

    result = provenance(issue(), metadata(raw, audits=(audit,)))

    assert result is not None
    assert result.revision == HEAD


def test_unbound_stale_unauthorized_and_superseded_overrides_fail_closed() -> None:
    assert provenance(issue(), metadata(override(selected_sha=None))) is None
    assert provenance(issue(), metadata(override(selected_sha=OLDER_HEAD))) is None
    assert (
        collect_owner_delivery_provenance(
            issue(),
            metadata(override(actor="former-owner")),
            project_id=PROJECT_ID,
            project=project(),
        )
        is None
    )
    # The newest applied row owns the generation.  An older matching row must
    # not be resurrected after a newer owner action names a different head.
    assert (
        provenance(
            issue(),
            metadata(override(), override(selected_sha=OLDER_HEAD)),
        )
        is None
    )


def test_malformed_and_lifecycle_reconciled_history_fail_closed() -> None:
    malformed = override()
    malformed["selected_sha"] = "not-a-revision"
    malformed_newer = override()
    malformed_newer.pop("target_state")
    reconciled = override()
    reconciled["lifecycle_reconciled"] = True

    assert provenance(issue(), metadata(malformed)) is None
    assert provenance(issue(), metadata(override(), malformed_newer)) is None
    assert provenance(issue(), metadata(reconciled)) is None


def test_owner_delivery_fact_avoids_landing_refresh_and_survives_restart(
    tmp_path,
) -> None:
    current = issue()
    owner_delivery = provenance(current, metadata(override()))
    assert owner_delivery is not None
    tracker = Tracker(current)
    sources = {
        FactDomain.TERMINAL_AUDIT: lambda _issue: {
            "phase": "completed",
            "owner_delivery": owner_delivery.to_dict(),
        }
    }
    database = tmp_path / "jobs.sqlite3"

    first_store = WorkflowJobStore(str(database))
    first_controller = IntegrationWorkflowController(
        collector=WorkflowFactCollector(
            project_id=PROJECT_ID,
            tracker=tracker,
            sources=sources,
            landing_collector=ForbiddenLandingCollector(),
            clock=lambda: NOW,
        ),
        store=first_store,
        landing_request_resolver=IntegrationLandingRequestResolver(
            project_id=PROJECT_ID,
            tracker=tracker,
            project_default_branch="main",
        ),
    )
    first_batch, first_scheduled = first_controller.reconcile([current])
    first_store.close()

    first = first_batch.tasks[0]
    assert first.facts.landings[0].state is LandingState.LANDED
    assert first.facts.landings[0].proof["authority"] == "project_owner_delivery"
    assert first.decision.reason_code == "terminal.immediate_target_landing_proven"
    assert first.decision.durable_jobs == ("parent_rollup_review",)
    assert first_scheduled.jobs_created == 1

    restarted_store = WorkflowJobStore(str(database))
    restarted_controller = IntegrationWorkflowController(
        collector=first_controller.collector,
        store=restarted_store,
        landing_request_resolver=first_controller.landing_request_resolver,
    )
    restarted_batch, restarted_scheduled = restarted_controller.reconcile([current])
    restarted_store.close()

    assert restarted_batch.tasks[0].decision.reason_code == (
        "terminal.immediate_target_landing_proven"
    )
    assert "integration_landing_refresh" not in (
        restarted_batch.tasks[0].decision.durable_jobs
    )
    assert restarted_scheduled.jobs_created == 0


def test_wrong_target_owner_fact_does_not_authorize_current_request() -> None:
    current = issue()
    owner_delivery = provenance(current, metadata(override()))
    assert owner_delivery is not None
    tracker = Tracker(current)
    collector = WorkflowFactCollector(
        project_id=PROJECT_ID,
        tracker=tracker,
        sources={
            FactDomain.TERMINAL_AUDIT: lambda _issue: {
                "owner_delivery": replace(
                    owner_delivery,
                    target="release/next",
                ).to_dict()
            }
        },
        clock=lambda: NOW,
    )

    facts = collector.collect(
        TASK_ID,
        landing_requests=(LandingRequest(TASK_ID, "main", HEAD),),
    )

    assert facts.landings == ()
    assert facts.fact(FactDomain.LANDING).error_code == (
        "landing_collector_unavailable"
    )


def test_target_drift_after_override_invalidates_provenance() -> None:
    original = issue(target="main")
    raw = override(fingerprint=compute_issue_evidence_fingerprint(original, PROJECT_ID))
    changed = issue(target="release/next")

    assert provenance(changed, metadata(raw)) is None
