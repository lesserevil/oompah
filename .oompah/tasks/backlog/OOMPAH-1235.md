---
id: OOMPAH-1235
type: task
status: Backlog
priority: null
title: Keep durable epic-rebase requests current across fresh evidence
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T11:41:26.466501Z'
updated_at: '2026-08-13T11:41:43.959403Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 96c6c71c-f5e8-436a-9c04-783dcf4e8200
  request_fingerprint: f621eb2015c79f16917e578bcd1e4a63083a743b75a4610e79367096749b1fba
---
## Summary

Live scheduling bug exposed by TRICKLE-138/139 after OOMPAH-1234 woke their queued nested topology repairs. When nested branch epic-TRICKLE-130 has unique commits, _request_nested_epic_lineage_repair emits epic_rebase_requested. EpicWorkflowEventRouter schedules epic_rebase_repair with expected_evidence_revision from an ephemeral current decision, but the production backend recollects fresh Git/containment evidence during revalidation; a benign revision change makes DurableWorkflowWorker supersede the job before creating a helper. Repeated identical requests then replay the terminal idempotency key, leaving children in repair retry_wait without a rebase helper. Implementation scope: bind event scheduling and revalidation to the same freshly recollected decision boundary, or explicitly make the rebase request target/source authority—not mutable collection revision—the currentness fence while preserving exact target, terminal status, source head, and generation protections. Ensure a superseded pre-fix request can materialize a new current generation rather than replaying a terminal key. Relevant files: oompah/epic_workflow_adapter.py, oompah/epic_workflow.py, workflow scheduling/worker code only if needed. Tests must reproduce a rebase event whose evidence revision changes between enqueue and revalidate, prove exactly one helper is created, preserve stale-target/source-head rejection and crash-replay idempotency, and cover replay after a terminal stale request. Acceptance: TRICKLE-130 receives one actionable rebase helper promptly, TRICKLE-138/139 stop cycling topology-repair backoff, focused epic/workflow tests and full branch CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 11:41
---
Claimed directly from live Trickle monitoring. OOMPAH-1234 successfully woke both old topology repairs; both correctly require a TRICKLE-130 rebase, but the epic-rebase event self-supersedes on freshly recollected evidence and replays its terminal idempotency key. Implementing and validating the systemic fix now; Oompah remains paused and only Trickle is resumed.
---
<!-- COMMENTS:END -->
