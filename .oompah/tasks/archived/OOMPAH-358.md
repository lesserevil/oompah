---
id: OOMPAH-358
type: task
status: Archived
priority: 1
title: Gate epic rebase scheduling on actionable conditions
parent: OOMPAH-356
children: []
blocked_by:
- OOMPAH-357
labels: []
assignee: null
created_at: '2026-07-22T01:23:51.390755Z'
updated_at: '2026-08-02T01:47:47.041372Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-82f090db2c15: '2026-08-02T01:47:41.051166+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-358
    target_state: Archived
    evidence_fingerprint: a95209a2e5e84d25e663b6c89792d61d9093b88b02f7b73fe663bca15169800e
    audit_ids:
    - audit-09c5d6e686c7
    kind: result
    applied: true
    retired_at: '2026-08-02T01:47:41.051174+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-358
    audit_id: audit-09c5d6e686c7
    attempt_id: attempt-82f090db2c15
    target_state: Archived
    evidence_fingerprint: a95209a2e5e84d25e663b6c89792d61d9093b88b02f7b73fe663bca15169800e
    status: Archived
    audit_ids:
    - audit-09c5d6e686c7
    applied: true
    created_at: '2026-08-02T01:47:41.051184+00:00'
    applied_at: '2026-08-02T01:47:46.044276+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-09c5d6e686c7
    project_id: proj-14849f1b
    task_id: OOMPAH-358
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a95209a2e5e84d25e663b6c89792d61d9093b88b02f7b73fe663bca15169800e
    attempts:
    - version: 1
      attempt_id: attempt-82f090db2c15
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a95209a2e5e84d25e663b6c89792d61d9093b88b02f7b73fe663bca15169800e
      created_at: '2026-08-02T01:35:46.804437+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:35:46.804437+00:00'
      branch_key: OOMPAH-358
      verdict: pass
      completed_at: '2026-08-02T01:47:41.051069+00:00'
      ended_at: '2026-08-02T01:47:41.051069+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:12:55.913861+00:00'
    updated_at: '2026-08-02T01:47:41.051069+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-82f090db2c15
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a95209a2e5e84d25e663b6c89792d61d9093b88b02f7b73fe663bca15169800e
    created_at: '2026-08-02T01:35:46.804437+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:35:46.804437+00:00'
    branch_key: OOMPAH-358
---
## Summary

Update the epic maintenance and rebase-dispatch flow to consume the synchronization policy. Preserve staleness detection, but make it observational by default. Do not create an agent task, worktree operation, merge, or rebase unless the policy returns an allowed actionable reason.\n\nImplementation scope:\n- Remove automatic rebase scheduling triggered only by commit-count/file-overlap staleness.\n- Retain configured threshold detection as an alert/signal.\n- Carry the actionable reason into logs, task comments, and rebase state.\n- Ensure PR-preparation and explicit operator paths can request an allowed synchronization.\n\nTests:\n- Integration-style tests proving stale incomplete epics cause no branch mutation or agent dispatch.\n- Tests proving PR preparation, explicit requests, and merge-blocking conflicts still schedule exactly one rebase.\n- Verify repeated ticks coalesce rather than repeatedly scheduling the same permitted rebase.\n\nAcceptance criteria:\n- Main advancing alone cannot generate a rebase agent for an unfinished epic.\n- Existing permitted rebase workflows remain functional and auditable.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:30
---
Removed periodic proactive rebase scheduling; staleness detection no longer creates branch-mutating work.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: removal of periodic proactive rebase scheduling is present on origin/main in commit 2ba37886b. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:27
---
Verified delivered on origin/main in 2ba37886b and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:12
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:35
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:35
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:47
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: 2ba37886b2f190fbfe84da6689e4a4f5877437fa
- delivery_subject: Stop automatic synchronization of unfinished epics
- origin_main_head: 6252b5434f392b74de9703a9fc8dca1951dfeaca
- focused_tests_epic_rebase_state: 33 passed in 11.69s
- focused_tests_orchestrator_handlers: 277 passed in 93.76s
- previous_state: Merged
- target_state: Archived
- auto_archive_source: auto_archive requested_by oompah, aged 7 days after Merged
---
<!-- COMMENTS:END -->
