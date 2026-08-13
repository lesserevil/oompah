---
id: OOMPAH-1240
type: task
status: In Validation
priority: null
title: Recognize persisted exact rebase helper during effect verification
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T13:41:09.711627Z'
updated_at: '2026-08-13T14:23:49.047944Z'
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
  creation_marker: 25732016-0297-4ace-8199-742af8cd985b
  request_fingerprint: 4aeb6b9dfd027b62fd73fa1488530a9fcc234dd203b9ffad5767533742151387
oompah.lifecycle_revision: 2
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-61cfe4e542d4
    project_id: proj-14849f1b
    task_id: OOMPAH-1240
    digest: 6cebaafc3b3a2908df46ce0d409fee309357dd7497b201b8907320f49cd37af0
  - version: 1
    audit_id: audit-41311a6c3f42
    project_id: proj-14849f1b
    task_id: OOMPAH-1240
    digest: 6cebaafc3b3a2908df46ce0d409fee309357dd7497b201b8907320f49cd37af0
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-61cfe4e542d4
    project_id: proj-14849f1b
    task_id: OOMPAH-1240
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6cebaafc3b3a2908df46ce0d409fee309357dd7497b201b8907320f49cd37af0
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T14:23:41.998978+00:00'
    eligible_at: '2026-08-13T14:23:41.998978+00:00'
    selected_ref: origin/OOMPAH-1240
    selected_sha: b5737d1bfa2159ba02adf986c36c944ef511eda0
  - version: 1
    audit_id: audit-41311a6c3f42
    project_id: proj-14849f1b
    task_id: OOMPAH-1240
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6cebaafc3b3a2908df46ce0d409fee309357dd7497b201b8907320f49cd37af0
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T14:23:41.998978+00:00'
    prerequisite_audit_id: audit-61cfe4e542d4
    selected_ref: origin/OOMPAH-1240
    selected_sha: b5737d1bfa2159ba02adf986c36c944ef511eda0
  attempt_history: []
---
## Summary

The v4 epic_rebase_repair workflow can atomically create or recover the authoritative helper and persist its exact identity, yet the durable job exhausts with 'epic_rebase_repair effect is not yet observable' when verification re-collects facts that do not expose that helper immediately. This was reproduced live on TRICKLE-130/TRICKLE-141 after deploying OOMPAH-1238 and OOMPAH-1239: workflow job sequence 16681 used target-source-head-immutable-helper-v4 and exhausted all five attempts even though the server's persisted epic-rebase authority names the valid active helper. Update the rebase observation/verification boundary to accept only the exact project-bound, parent-bound, source-generation-bound, target-bound helper identity persisted by the server; forged/title-only helpers must remain rejected. Add regression tests covering create/recover receipt followed by stale child projection, eventual projection, wrong task/project/parent/target/source generation, and retry/restart idempotency. Acceptance: the live-equivalent v4 job completes or is safely superseded once the exact helper is durable, without duplicate helpers or weakening CAS authority, and focused workflow/rebase tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 13:59
---
Implemented regression coverage and repair: bind implicit native Markdown project scope before exact-helper observation/receipt verification, reject conflicting explicit scope, and bump the durable revalidation contract so exhausted pre-fix repairs replay after deployment. Focused workflow/epic suite: 485 passed; terminal mutation scan and secret scan passed.
---
author: oompah
created: 2026-08-13 14:23
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
