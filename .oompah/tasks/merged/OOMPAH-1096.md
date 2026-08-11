---
id: OOMPAH-1096
type: task
status: Merged
priority: null
title: Prevent unrelated tracker churn from starving exact Ready-work publication
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T17:33:22.243112Z'
updated_at: '2026-08-11T18:39:21.990679Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 9bd7eafe-8b80-4e48-830b-3a29b5bfa538
  request_fingerprint: 99c02ef95efb85612c63db568b0bc0b8a0c40ff0fd752d3bcd2746f9bc53f74d
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-52efdfa0ca1f
    project_id: proj-14849f1b
    task_id: OOMPAH-1096
    digest: 9f7059edfc9d272bdfce47d9d094189c5a92a3deb668d215f38856b11b00ad0e
  - version: 1
    audit_id: audit-66ad28f540eb
    project_id: proj-14849f1b
    task_id: OOMPAH-1096
    digest: 9f7059edfc9d272bdfce47d9d094189c5a92a3deb668d215f38856b11b00ad0e
  oompah.terminal_override_records:
  - version: 1
    override_id: override-d3cb47716ee3
    project_id: proj-14849f1b
    task_id: OOMPAH-1096
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9f7059edfc9d272bdfce47d9d094189c5a92a3deb668d215f38856b11b00ad0e
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Operator-directed manual completion while all Oompah schedulers are paused:
      independent exact-head audit ACCEPT at 1cade67f25011c1e94df187f737957d5e8bad67b;
      161 runtime and 94 adjacent tests, 25 repeated race/restart runs, bounded 120-task
      workflow soak, and terminal audit scan passed; protected GitHub CI succeeded
      on Python 3.11, 3.12, and 3.13; PR #833 merged as 2c010f7b800a1bf0053baf95c2998eda74d3cd3b;
      exact head is contained in origin/main.'
    created_at: '2026-08-11T18:39:14.465702+00:00'
    selected_ref: origin/OOMPAH-1096
    selected_sha: 1cade67f25011c1e94df187f737957d5e8bad67b
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-52efdfa0ca1f
    project_id: proj-14849f1b
    task_id: OOMPAH-1096
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9f7059edfc9d272bdfce47d9d094189c5a92a3deb668d215f38856b11b00ad0e
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-11T18:38:28.371944+00:00'
    eligible_at: '2026-08-11T18:38:28.371944+00:00'
    selected_ref: origin/OOMPAH-1096
    selected_sha: 1cade67f25011c1e94df187f737957d5e8bad67b
  - version: 1
    audit_id: audit-66ad28f540eb
    project_id: proj-14849f1b
    task_id: OOMPAH-1096
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9f7059edfc9d272bdfce47d9d094189c5a92a3deb668d215f38856b11b00ad0e
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-11T18:38:28.371944+00:00'
    prerequisite_audit_id: audit-52efdfa0ca1f
    selected_ref: origin/OOMPAH-1096
    selected_sha: 1cade67f25011c1e94df187f737957d5e8bad67b
  attempt_history: []
---
## Summary

Bug observed live on 2026-08-11: workflow jobs 5180 (OOMPAH-1091 review_merge), 5181 (OOMPAH-1085 standalone_delivery), and 5182 (OOMPAH-1095 standalone_delivery) were all superseded at 17:27:53 UTC with 'workflow snapshot publication did not commit' while unrelated terminal auditors were posting task/comment/status updates. Exact heads remained unchanged; PRs #827 and #830 were clean with all protected CI green, yet no replacement intent was materialized beyond the configured review reassessment window. Implementation scope: workflow snapshot publication/reconciliation and exact durable job materialization. Prevent unrelated project tracker revision churn from starving a task whose own evidence/authority is unchanged. Preserve fail-closed behavior for relevant task/head/authority changes, exact idempotency, and no duplicate forge effects. Add deterministic concurrency tests with continuous unrelated task/comment churn proving the eligible task publishes/requeues a current exact job within its bounded SLO, plus restart/retry coverage. Acceptance: eligible Ready/In Review work progresses during unrelated tracker churn; relevant evidence drift still supersedes stale work; observability distinguishes bounded retry from overdue starvation; full focused workflow/publication tests and workflow soak pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 17:48
---
Implementation is committed and pushed at exact head 1cade67f25011c1e94df187f737957d5e8bad67b on branch OOMPAH-1096, rebased patch-equivalently onto current origin/main b948150a8. The workflow snapshot publisher now consumes the existing managed per-task publication journal: a final revision advance is accepted only when the journal is complete, the delta is nonempty and exactly matches the observed counter, at least one exact durable action is staged, and every changed task is disjoint from staged effect identities and dependency targets. Journal-proven unrelated tasks are excluded from the projection and mark the liveness cut intentionally incomplete; exact task drift, dependency drift, ambiguous membership, missing history, and unknown scope still supersede and retry the whole generation. Observability records tracker_scoped_publication_advances/exclusions separately from scoped_publication_retries. Deterministic regressions cover a 64-write continuous unrelated burst publishing review_merge on the first cut, relevant exact-task drift forcing a fresh generation, durable-store restart reusing one exact job, and health projection remaining non-overdue. Verification after rebase: 446 focused workflow job/controller/runtime/cache/tracker-lock tests passed; make workflow-soak-ci completed 120 tasks with 380 projection checks, 0 mismatches, 1 expected actionable alert, and no unexplained tasks; make terminal-audit-scan passed 21/21; py_compile, diff check, secret hooks, and range-diff clean. No full 20k gate was run per handoff. Not submitted; awaiting independent exact-head review.
---
author: oompah
created: 2026-08-11 18:38
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
