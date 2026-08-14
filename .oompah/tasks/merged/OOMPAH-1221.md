---
id: OOMPAH-1221
type: task
status: Merged
priority: null
title: Accepted integration submissions must preempt implementation dispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T05:19:06.019608Z'
updated_at: '2026-08-14T07:31:43.703834Z'
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
  creation_marker: e27c0303-bd1e-4eda-a993-267b894fdfa2
  request_fingerprint: 5111a3df750124b1bb3921dfea79e59f57e7038b91724e04203367574ce50d73
oompah.lifecycle_revision: 3
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-6f49271d6f30
    project_id: proj-14849f1b
    task_id: OOMPAH-1221
    digest: 07abc04abb2cda0e368bc6198ef28ab814d73a0d759968559560e2fa29adc2ce
  - version: 1
    audit_id: audit-aaef2de0c841
    project_id: proj-14849f1b
    task_id: OOMPAH-1221
    digest: 07abc04abb2cda0e368bc6198ef28ab814d73a0d759968559560e2fa29adc2ce
  oompah.terminal_override_records:
  - version: 1
    override_id: override-6533e3ca4409
    project_id: proj-14849f1b
    task_id: OOMPAH-1221
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 07abc04abb2cda0e368bc6198ef28ab814d73a0d759968559560e2fa29adc2ce
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #851 merged as 4eb4dc678 and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:31:34.417082+00:00'
    selected_ref: origin/OOMPAH-1221
    selected_sha: 27c9bd1ae4fa35310ca8abaf4e56a844990d4963
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1221
    target_state: Merged
    evidence_fingerprint: 07abc04abb2cda0e368bc6198ef28ab814d73a0d759968559560e2fa29adc2ce
    workflow_revision: null
    selected_ref: origin/OOMPAH-1221
    selected_sha: 27c9bd1ae4fa35310ca8abaf4e56a844990d4963
    landing_revision: null
    audit_ids:
    - audit-6f49271d6f30
    - audit-aaef2de0c841
    kind: override
    applied: true
    retired_at: '2026-08-14T07:31:42.575032+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-6f49271d6f30
    project_id: proj-14849f1b
    task_id: OOMPAH-1221
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 07abc04abb2cda0e368bc6198ef28ab814d73a0d759968559560e2fa29adc2ce
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T06:05:49.466643+00:00'
    eligible_at: '2026-08-13T06:05:49.466643+00:00'
    selected_ref: origin/OOMPAH-1221
    selected_sha: 27c9bd1ae4fa35310ca8abaf4e56a844990d4963
    updated_at: '2026-08-14T07:31:42.574989+00:00'
  - version: 1
    audit_id: audit-aaef2de0c841
    project_id: proj-14849f1b
    task_id: OOMPAH-1221
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 07abc04abb2cda0e368bc6198ef28ab814d73a0d759968559560e2fa29adc2ce
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T06:05:49.466643+00:00'
    prerequisite_audit_id: audit-6f49271d6f30
    selected_ref: origin/OOMPAH-1221
    selected_sha: 27c9bd1ae4fa35310ca8abaf4e56a844990d4963
    updated_at: '2026-08-14T07:31:42.575014+00:00'
  attempt_history: []
---
## Summary

Bug: a task can carry an exact accepted integration record (integration.state=ready with branch/head/submitted_at) while tracker status remains Open or In Progress after a transition race or restart. The implementation decision currently ignores that accepted delivery authority for ordinary work, emits implementation_start/recovery, and eventually exhausts retries. Live examples on 2026-08-13 included TRICKLE-118/119/121/124/131/135 and redundant redispatch of TRICKLE-120/132/133. Scope: make exact accepted integration authority win before implementation eligibility/recovery and transition the task to Ready to Integrate through the generation-fenced transition service; suppress or supersede stale implementation jobs and revoke any redundant running implementation authority. Relevant code: oompah/work_decision.py, workflow controller/runtime/adapters, transition guards. Tests must reproduce Open and In Progress tasks with accepted standalone and queue submissions, restart reconstruction, exhaustion history, and a race where submission lands between decision publication and worker admission. Acceptance: accepted work is never reimplemented, task converges to Ready to Integrate, integration-owned jobs are materialized, stale implementation jobs/agents cannot mutate, alerts clear without operator action, and all focused/full tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 05:19
---
Claiming directly. The live reproduction has six exhausted completed submissions plus three redundant implementations admitted after restart; OOMPAH-1218 prevents status drift for new assignment transitions but accepted submission authority still needs to preempt implementation decisions.
---
author: oompah
created: 2026-08-13 05:58
---
Implemented and pushed 27c9bd1ae with PR #851. Accepted integration records now preempt implementation decisions and final worker admission; restart reconstruction materializes exact validation-submission recovery; Open recovery is restricted to orchestration authority. Verification: 541 focused tests passed, secret scan passed, and the broad gate reached 4,423 passing tests before it was restarted for the final authority-fence edit. Hosted Python 3.11/3.12/3.13 checks are running.
---
author: oompah
created: 2026-08-13 06:06
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 07:31
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner convergence: PR #851 merged as 4eb4dc678 and that landed tree is contained by origin/main; this stale non-terminal projection requires no further implementation.
---
<!-- COMMENTS:END -->
