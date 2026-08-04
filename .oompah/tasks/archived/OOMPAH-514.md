---
id: OOMPAH-514
type: chore
status: Archived
priority: 1
title: Prove maintenance cannot dirty or push the server code checkout
parent: OOMPAH-511
children: []
blocked_by:
- OOMPAH-512
- OOMPAH-513
labels: []
assignee: null
created_at: '2026-07-28T15:16:44.915690Z'
updated_at: '2026-08-04T16:41:46.188818Z'
work_branch: epic-OOMPAH-511
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 695b9b0e-146c-419d-a026-9b0adefe1d92
oompah.work_branch: epic-OOMPAH-511
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-50abb3ffc64d: '2026-08-04T16:41:42.508768+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-514
    target_state: Archived
    evidence_fingerprint: 22445caa8c8b73dcb16d7959adc53991fff2bbf5e9e7076ae79f17a72e360881
    audit_ids:
    - audit-96a8011ef3fe
    kind: result
    applied: true
    retired_at: '2026-08-04T16:41:42.508779+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-514
    audit_id: audit-96a8011ef3fe
    attempt_id: attempt-50abb3ffc64d
    target_state: Archived
    evidence_fingerprint: 22445caa8c8b73dcb16d7959adc53991fff2bbf5e9e7076ae79f17a72e360881
    status: Archived
    audit_ids:
    - audit-96a8011ef3fe
    applied: false
    created_at: '2026-08-04T16:41:42.508793+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-96a8011ef3fe
    project_id: proj-14849f1b
    task_id: OOMPAH-514
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 22445caa8c8b73dcb16d7959adc53991fff2bbf5e9e7076ae79f17a72e360881
    attempts:
    - version: 1
      attempt_id: attempt-50abb3ffc64d
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 22445caa8c8b73dcb16d7959adc53991fff2bbf5e9e7076ae79f17a72e360881
      created_at: '2026-08-04T16:38:20.406622+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T16:38:20.406622+00:00'
      branch_key: epic-OOMPAH-511
      verdict: pass
      completed_at: '2026-08-04T16:41:42.508594+00:00'
      ended_at: '2026-08-04T16:41:42.508594+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T16:25:00.158393+00:00'
    updated_at: '2026-08-04T16:41:42.508594+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-50abb3ffc64d
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 22445caa8c8b73dcb16d7959adc53991fff2bbf5e9e7076ae79f17a72e360881
    created_at: '2026-08-04T16:38:20.406622+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T16:38:20.406622+00:00'
    branch_key: epic-OOMPAH-511
---
## Summary

Implementation scope

Add an end-to-end regression around scheduler/background maintenance and representative server-side tracker consumers. Build disposable local Git repositories with separate code and Oompah state branches, register the project, run maintenance ticks including archive/error-watcher style mutations, and verify all durable task changes land only on the state branch. Exercise an ambiguous or missing-project context and verify it fails closed. Ensure executor-backed maintenance futures are joined or cancelled by the test harness so no work escapes after the test finishes. This task complements OOMPAH-492; do not re-edit its specifically assigned worker-exit, ACP billing, or epic-rebase cases unless its completed result requires integration adjustment.

Relevant files

tests for the orchestrator event loop/maintenance, native state-branch E2E suites, server fixtures, and the smallest production cleanup needed to make background lifecycle ownership deterministic.

Required tests

Assert the code checkout HEAD, worktree, index, and origin/default ref are unchanged before/after maintenance; assert the state branch contains the expected task update; assert no child process or pending executor future remains; run the focused E2E tests repeatedly and run make test from a clean isolated worktree.

Acceptance criteria

Maintenance and server helpers cannot write or push task metadata to the code branch, ambiguous project context produces no mutation, all asynchronous work is accounted for before teardown, the regression is deterministic across repeated runs, and the full suite passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:38
---
Claimed in the OOMPAH-511 isolated worktree. Added disposable-remote regression coverage for state-only maintenance writes and orchestrator shutdown drainage; the full project test suite is running.
---
author: oompah
created: 2026-07-28 15:41
---
Completed in commit 6533e235e. A disposable bare-remote integration test proves auto-archive changes only the configured state ref while local/remote main and the code checkout remain unchanged. Orchestrator shutdown now drains maintenance futures and owned executor pools. make test: 12,402 passed, 39 skipped; make check-secrets passed.
---
author: oompah
created: 2026-07-28 15:42
---
Added deterministic maintenance/state-branch Git isolation coverage and shutdown drainage for background work.
---
author: oompah
created: 2026-07-28 16:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 16:02
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 16:02
---
Agent failed: errored. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-28 16:02
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/fable]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 5s
- Log: OOMPAH-514__20260728T160228Z.jsonl
---
author: oompah
created: 2026-07-28 16:02
---
Agent dispatched (profile: quick)
---
author: oompah
created: 2026-07-28 16:02
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 16:03
---
Understanding: I will audit the existing OOMPAH-511 maintenance/state-branch changes against OOMPAH-514's stronger end-to-end requirements, run focused regressions repeatedly, inspect lifecycle and ambiguous-context coverage, and add only any missing deterministic assertions before full verification.
---
author: oompah
created: 2026-07-28 16:07
---
Run #2 [attempt=2, profile=quick, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 39
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 40s
- Log: OOMPAH-514__20260728T160250Z.jsonl
---
author: oompah
created: 2026-07-28 16:07
---
Implementation: expanded tests/test_managed_tracker_state_branch_guard.py with full code HEAD/worktree/index/local-origin/remote-main snapshots, explicit ambiguous unscoped-issue fail-closed coverage, actual server.set_orchestrator ErrorWatcher routing plus scheduler archive mutation, state-branch diff assertions, and a blocked _tick() maintenance future that stop() must drain before owned executor threads disappear.
---
author: oompah
created: 2026-07-28 16:07
---
Agent dispatched (profile: quick)
---
author: oompah
created: 2026-07-28 16:07
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 16:15
---
Verification: focused state-branch regression passes 19/19 across three consecutive runs; related suites pass 440/440 except two environment-overridden full-sync config assertions; equivalent full pytest passes 12,631 with 7 skipped and one unrelated read-only agent-log failure, which passes when OOMPAH_AGENT_LOG_DIR points to /tmp. make check-secrets passes. make test itself cannot start because uv transient-scope DBus setup error (exit 46).
---
author: oompah
created: 2026-07-28 16:16
---
Completion: pushed 5397b7a82 to origin/epic-OOMPAH-511. The regression now covers server ErrorWatcher routing, scheduler archive writes, exact code HEAD/worktree/index/origin-main/remote-main invariants, remote state-branch task contents, ambiguous/missing-project fail-closed behavior, and stop() drainage of maintenance futures and owned executor threads. Focused tests pass 19/19 in three repeats; full equivalent pytest passes 12,631 with the documented read-only agent-log environment failure resolved via OOMPAH_AGENT_LOG_DIR=/tmp; make check-secrets passes.
---
author: oompah
created: 2026-07-28 16:16
---
Run #2 [attempt=2, profile=quick, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 25
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 39s
- Log: OOMPAH-514__20260728T160754Z.jsonl
---
author: oompah
created: 2026-07-28 16:16
---
Added and pushed deterministic server/scheduler state-branch isolation and executor-drainage regressions.
---
author: oompah
created: 2026-08-04 16:25
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 16:38
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 16:38
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
