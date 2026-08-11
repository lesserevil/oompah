---
id: OOMPAH-1076
type: task
status: Open
priority: null
title: Bound large-corpus workflow reconciliation within restart SLO
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T09:41:07.342509Z'
updated_at: '2026-08-11T10:52:44.850972Z'
work_branch: OOMPAH-1076
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/814
review_number: '814'
review_head: 6bfbd416cd2934cd4a2d04959567e8a50e0f0a35
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 0bd548a4-8b7b-45c6-b787-41efab3e0d67
  request_fingerprint: 5ea2f35f9115133371ebbc0341e287e822a967ee1c6968758bc9be0582b7a261
oompah.review_url: https://github.com/lesserevil/oompah/pull/814
oompah.review_number: '814'
oompah.work_branch: OOMPAH-1076
oompah.target_branch: main
oompah.review_head: 6bfbd416cd2934cd4a2d04959567e8a50e0f0a35
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-7fe3fcb0020d
    project_id: proj-14849f1b
    task_id: OOMPAH-1076
    digest: 4fd9146b1adbf6f8266e43f47ed727692028607cb9faa9ec688515281b35d70b
  - version: 1
    audit_id: audit-a27fa4e3d94b
    project_id: proj-14849f1b
    task_id: OOMPAH-1076
    digest: 4fd9146b1adbf6f8266e43f47ed727692028607cb9faa9ec688515281b35d70b
  oompah.terminal_override_records:
  - version: 1
    override_id: override-e63e8b1f7e78
    project_id: proj-14849f1b
    task_id: OOMPAH-1076
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4fd9146b1adbf6f8266e43f47ed727692028607cb9faa9ec688515281b35d70b
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner revision boundary: revision 1 exact head 6bfbd416cd2934cd4a2d04959567e8a50e0f0a35
      passed the 170.2s branch gate, independent review, protected Python 3.11/3.12/3.13
      CI, and merged through PR 814 as db20b747bbd61f27bafd61a4ea71ebe2d74918b3. The
      deployed live canary subsequently exposed a remaining integration/epic cold-path
      SLO failure; terminalize only revision 1 so a new auditable revision can immediately
      continue the same task.'
    created_at: '2026-08-11T10:51:30.414958+00:00'
    selected_ref: origin/OOMPAH-1076
    selected_sha: 6bfbd416cd2934cd4a2d04959567e8a50e0f0a35
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1076
    target_state: Merged
    evidence_fingerprint: 4fd9146b1adbf6f8266e43f47ed727692028607cb9faa9ec688515281b35d70b
    workflow_revision: null
    selected_ref: origin/OOMPAH-1076
    selected_sha: 6bfbd416cd2934cd4a2d04959567e8a50e0f0a35
    landing_revision: null
    audit_ids:
    - audit-7fe3fcb0020d
    - audit-a27fa4e3d94b
    kind: override
    applied: true
    retired_at: '2026-08-11T10:51:39.426618+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: false
    authority_generation: 1
    reason: Retain merged revision 1 as provenance while authorizing the live-canary
      follow-up revision on the same task.
    marked_at: '2026-08-11T10:52:27.705720+00:00'
    updated_at: '2026-08-11T10:52:43.230728+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Retain merged revision 1 as provenance while authorizing the live-canary
        follow-up revision on the same task.
      recorded_at: '2026-08-11T10:52:27.705720+00:00'
      authority_generation: 0
    - kind: revise
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Deployed revision 1 improved generic containment but the live 1,882-issue
        canary still took 130.1 seconds of reconciliation phases; continue with revision
        2 targeting measured integration=100.37s and epic=27.25s.
      recorded_at: '2026-08-11T10:52:43.230728+00:00'
      authority_generation: 1
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-7fe3fcb0020d
    project_id: proj-14849f1b
    task_id: OOMPAH-1076
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4fd9146b1adbf6f8266e43f47ed727692028607cb9faa9ec688515281b35d70b
    attempts:
    - version: 1
      attempt_id: attempt-9ad1d8c664f3
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 4fd9146b1adbf6f8266e43f47ed727692028607cb9faa9ec688515281b35d70b
      created_at: '2026-08-11T10:47:18.920819+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T10:47:18.920819+00:00'
      branch_key: OOMPAH-1076
      selected_ref: origin/OOMPAH-1076
      selected_sha: 6bfbd416cd2934cd4a2d04959567e8a50e0f0a35
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T10:28:32.737789+00:00'
    selected_ref: origin/OOMPAH-1076
    selected_sha: 6bfbd416cd2934cd4a2d04959567e8a50e0f0a35
    updated_at: '2026-08-11T10:51:39.426571+00:00'
  - version: 1
    audit_id: audit-a27fa4e3d94b
    project_id: proj-14849f1b
    task_id: OOMPAH-1076
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4fd9146b1adbf6f8266e43f47ed727692028607cb9faa9ec688515281b35d70b
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T10:28:32.737789+00:00'
    selected_ref: origin/OOMPAH-1076
    selected_sha: 6bfbd416cd2934cd4a2d04959567e8a50e0f0a35
    updated_at: '2026-08-11T10:51:39.426602+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-9ad1d8c664f3
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4fd9146b1adbf6f8266e43f47ed727692028607cb9faa9ec688515281b35d70b
    created_at: '2026-08-11T10:47:18.920819+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T10:47:18.920819+00:00'
    branch_key: OOMPAH-1076
    selected_ref: origin/OOMPAH-1076
    selected_sha: 6bfbd416cd2934cd4a2d04959567e8a50e0f0a35
oompah.task_costs:
  total_input_tokens: 814
  total_output_tokens: 211
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 814
      output_tokens: 211
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 814
    output_tokens: 211
    cost_usd: 0.0
    recorded_at: '2026-08-11T10:51:45.702107+00:00'
---
## Summary

Live regression observed 2026-08-11 after the OOMPAH-1075 cache-generation correction was prepared: a full WorkflowRuntime reconciliation over 1,878 tasks consumes roughly 138-215 seconds of one executor CPU core before publication. The server event loop remains responsive and publication locks show zero wait, but restart reconstruction has a 120-second deadline; the monolithic cut therefore becomes restart_overdue even without lock contention, and any legitimate authority change can discard minutes of work. This is distinct from OOMPAH-969 prompt effect admission, OOMPAH-986 terminal-audit scoped publication, and OOMPAH-1075 false read-cache generation churn. Implementation scope: instrument and bound full-corpus collection, then optimize, chunk, or retain/retry stable project/task work so a restart can publish a complete authoritative snapshot within 120 seconds under ordinary concurrent tracker activity. Preserve fail-closed same-task/project authority, atomic durable snapshot/effect publication, pause/quiesce behavior, worker admission fencing, and terminal-audit/review exactness. Relevant code: oompah/workflow_runtime.py and its domain collectors/native tracker access paths. Required tests: deterministic large-corpus restart with a concurrent three-minute branch gate and ordinary tracker mutation; prove a fresh complete snapshot publishes and restart_pending clears within 120 seconds while admission remains fail-closed until it does; prove affected authority is recomputed without duplicating effects; prove event-loop/control endpoints remain responsive; include performance/phase telemetry that identifies regressions. Acceptance: the live-equivalent 1,878-task canary publishes a complete current snapshot inside the configured 120-second restart SLO, repeated ordinary mutations cannot indefinitely starve it, focused workflow/native-tracker tests and protected CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 09:47
---
Design checkpoint: the dominant 1,878-task cost is generic containment scanning the full authoritative issue map per task, compounded by collecting generic liveness facts before overwriting them with owning-domain facts. Implementing a per-project child index plus collect-only-missing liveness facts. Concurrent ordinary tracker mutations will use exact scoped change journaling to retry only the affected project before snapshot/effect acceptance, followed by a stable-project-preserving correction sweep; ambiguous or dependency-sensitive authority remains fail-closed. Adding phase/correction telemetry and deterministic large-corpus/concurrent-mutation coverage while preserving OOMPAH-969 admission isolation, OOMPAH-974 cooperative control, and OOMPAH-986 terminal-audit proofs.
---
author: oompah
created: 2026-08-11 10:22
---
Branch quality gate passed for `6bfbd416cd2934cd4a2d04959567e8a50e0f0a35` using `make test` in 170.2s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 10:28
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 10:47
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 10:47
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 10:50
---
Live acceptance failed on deployed db20b747: the 1,882-issue cold reconstruction published after about 130.1s of reconciliation phases (141.1s tick), exceeding the 120s SLO. Phase telemetry isolates integration at 100.37s and epic at 27.25s; implementation/liveness/indexing are sub-second. Returning this task to active implementation and cancelling terminalization while the native-Git integration/epic cold path is optimized and re-canary-tested.
---
author: oompah
created: 2026-08-11 10:51
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Project-owner revision boundary: revision 1 exact head 6bfbd416cd2934cd4a2d04959567e8a50e0f0a35 passed the 170.2s branch gate, independent review, protected Python 3.11/3.12/3.13 CI, and merged through PR 814 as db20b747bbd61f27bafd61a4ea71ebe2d74918b3. The deployed live canary subsequently exposed a remaining integration/epic cold-path SLO failure; terminalize only revision 1 so a new auditable revision can immediately continue the same task.
---
author: oompah
created: 2026-08-11 10:51
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 50
- Tokens: 814 in / 211 out [1.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 24s
- Log: OOMPAH-1076__20260811T104733Z.jsonl
---
<!-- COMMENTS:END -->
