---
id: OOMPAH-401
type: task
status: Archived
priority: null
title: Preserve structured Markdown descriptions in native tasks
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T05:18:51.142416Z'
updated_at: '2026-08-02T01:28:03.502794Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-ad95c6306b68: '2026-08-02T01:28:00.386124+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-401
    target_state: Archived
    evidence_fingerprint: 0778b90cc2cbd0fa88ab81c667deca6b497b4306e9d806748507cacd3d2cce9f
    audit_ids:
    - audit-da556e0797a9
    kind: result
    applied: true
    retired_at: '2026-08-02T01:28:00.386132+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-401
    audit_id: audit-da556e0797a9
    attempt_id: attempt-ad95c6306b68
    target_state: Archived
    evidence_fingerprint: 0778b90cc2cbd0fa88ab81c667deca6b497b4306e9d806748507cacd3d2cce9f
    status: Archived
    audit_ids:
    - audit-da556e0797a9
    applied: false
    created_at: '2026-08-02T01:28:00.386143+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-da556e0797a9
    project_id: proj-14849f1b
    task_id: OOMPAH-401
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0778b90cc2cbd0fa88ab81c667deca6b497b4306e9d806748507cacd3d2cce9f
    attempts:
    - version: 1
      attempt_id: attempt-ad95c6306b68
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0778b90cc2cbd0fa88ab81c667deca6b497b4306e9d806748507cacd3d2cce9f
      created_at: '2026-08-02T01:15:45.384105+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:15:45.384105+00:00'
      branch_key: OOMPAH-401
      verdict: pass
      completed_at: '2026-08-02T01:28:00.386014+00:00'
      ended_at: '2026-08-02T01:28:00.386014+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:07.201134+00:00'
    updated_at: '2026-08-02T01:28:00.386014+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ad95c6306b68
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0778b90cc2cbd0fa88ab81c667deca6b497b4306e9d806748507cacd3d2cce9f
    created_at: '2026-08-02T01:15:45.384105+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:15:45.384105+00:00'
    branch_key: OOMPAH-401
---
## Summary

Prevent native Markdown task creation from storing a non-empty structured Markdown description that the tracker later parses as empty. Normalize H1/H2 headings before embedding descriptions in the Summary section, validate the resulting parsed description, and add regression tests. Repair OOMPAH-308 through OOMPAH-313 so their existing structured content remains intact and their parsed descriptions are non-empty. Acceptance: structured Markdown task creation yields a non-empty API description; blank normalized descriptions are rejected; the six affected tasks are repaired through the task API; relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:22
---
Implemented and verified: native task creation and description updates now demote H1/H2 headings before embedding them in Summary, preventing structured Markdown from parsing as an empty description. The API now rejects promotion to a dispatchable status when the normalized description is empty. Repaired OOMPAH-308 through OOMPAH-313 via the task API; each now exposes a non-empty parsed description. make test passed.
---
author: oompah
created: 2026-07-22 05:22
---
Implemented native structured-description safeguards, repaired the six affected tasks, and passed make test.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: structured native task description preservation and validation is present on origin/main in commit dcbef393e. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:28
---
Verified delivered on origin/main in dcbef393e and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:13
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:15
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:15
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:28
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: dcbef393e5ed5c110c4413f224f02e0a227d1df0
- head_sha: 6252b5434f392b74de9703a9fc8dca1951dfeaca
- tracker_helper_symbol: oompah/oompah_md_tracker.py:_summary_safe_description@173
- server_validation_symbol: oompah/server.py:api_update_issue (validation of empty description on dispatchable status)
- regression_tests: tests/test_oompah_md_tracker.py:110,126; tests/test_server_source_update.py:127
- previous_state: Merged
- aged_merged_reason: Auto-archive queued 2026-08-02 for task closed 2026-07-22 (>=7 days)
- pytest_run_here: not-run: auditor policy blocked env-var-set invocation and pytest reported ImportPathMismatchError in this worktree layout; delivery commit's tests were validated at merge time
---
<!-- COMMENTS:END -->
