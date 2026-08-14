---
id: OOMPAH-1235
type: task
status: Merged
priority: null
title: Keep durable epic-rebase requests current across fresh evidence
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T11:41:26.466501Z'
updated_at: '2026-08-14T07:39:18.911568Z'
work_branch: OOMPAH-1235
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
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1235
  head_sha: 1599a811c60c72908f41b0a7779ba46fb5cd4cc6
  submitted_at: '2026-08-13T11:46:44.254093+00:00'
  updated_at: '2026-08-13T11:46:44.254093+00:00'
oompah.work_branch: OOMPAH-1235
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-d7132be309d9
    project_id: proj-14849f1b
    task_id: OOMPAH-1235
    digest: d540ab0f4f7e9d38e392a710d52f7df05cfa9a9bd2326744296effc447ec2888
  - version: 1
    audit_id: audit-f105a93d7779
    project_id: proj-14849f1b
    task_id: OOMPAH-1235
    digest: d540ab0f4f7e9d38e392a710d52f7df05cfa9a9bd2326744296effc447ec2888
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7f39645a41df
    project_id: proj-14849f1b
    task_id: OOMPAH-1235
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d540ab0f4f7e9d38e392a710d52f7df05cfa9a9bd2326744296effc447ec2888
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #862 merged as f2637b9b8 and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:39:10.110330+00:00'
    selected_ref: 1599a811c60c72908f41b0a7779ba46fb5cd4cc6
    selected_sha: 1599a811c60c72908f41b0a7779ba46fb5cd4cc6
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1235
    target_state: Merged
    evidence_fingerprint: d540ab0f4f7e9d38e392a710d52f7df05cfa9a9bd2326744296effc447ec2888
    workflow_revision: null
    selected_ref: 1599a811c60c72908f41b0a7779ba46fb5cd4cc6
    selected_sha: 1599a811c60c72908f41b0a7779ba46fb5cd4cc6
    landing_revision: null
    audit_ids:
    - audit-d7132be309d9
    - audit-f105a93d7779
    kind: override
    applied: true
    retired_at: '2026-08-14T07:39:17.761389+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-d7132be309d9
    project_id: proj-14849f1b
    task_id: OOMPAH-1235
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d540ab0f4f7e9d38e392a710d52f7df05cfa9a9bd2326744296effc447ec2888
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T11:56:13.412037+00:00'
    eligible_at: '2026-08-13T11:56:13.412037+00:00'
    selected_ref: 1599a811c60c72908f41b0a7779ba46fb5cd4cc6
    selected_sha: 1599a811c60c72908f41b0a7779ba46fb5cd4cc6
    updated_at: '2026-08-14T07:39:17.761338+00:00'
  - version: 1
    audit_id: audit-f105a93d7779
    project_id: proj-14849f1b
    task_id: OOMPAH-1235
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d540ab0f4f7e9d38e392a710d52f7df05cfa9a9bd2326744296effc447ec2888
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T11:56:13.412037+00:00'
    prerequisite_audit_id: audit-d7132be309d9
    selected_ref: 1599a811c60c72908f41b0a7779ba46fb5cd4cc6
    selected_sha: 1599a811c60c72908f41b0a7779ba46fb5cd4cc6
    updated_at: '2026-08-14T07:39:17.761369+00:00'
  attempt_history: []
oompah.lifecycle_revision: 2
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
author: oompah
created: 2026-08-13 11:46
---
Implementation complete. Rebase events now use exact target/source/epic authority rather than mutable collection revision, backend accepts a fresh revision when rebase remains currently authorized, and v2 event identity avoids replay of the stranded terminal request. Focused epic/workflow suite: 494 passed; terminal mutation and secret scans passed.
---
author: oompah
created: 2026-08-13 11:46
---
Prevent durable epic-rebase requests from self-superseding on benign evidence refresh; version event identity to recover stranded terminal requests. 494 focused tests and repository scans pass.
---
author: oompah
created: 2026-08-13 11:56
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 07:39
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner convergence: PR #862 merged as f2637b9b8 and that landed tree is contained by origin/main; this stale non-terminal projection requires no further implementation.
---
<!-- COMMENTS:END -->
