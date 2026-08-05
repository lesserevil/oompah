---
id: OOMPAH-547
type: feature
status: Archived
priority: 0
title: Split finish-order dependencies from hard-start dependencies
parent: OOMPAH-545
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:09.212852Z'
updated_at: '2026-08-05T19:58:26.441973Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-4f67416d79d3: '2026-08-05T19:58:14.458427+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-547
    target_state: Archived
    evidence_fingerprint: c8b328d5d2241833249df78e198cc72eebc38bf733d4beb50d190fb371a20d52
    audit_ids:
    - audit-b8bec3b781cd
    kind: result
    applied: true
    retired_at: '2026-08-05T19:58:14.458441+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-547
    audit_id: audit-b8bec3b781cd
    attempt_id: attempt-4f67416d79d3
    target_state: Archived
    evidence_fingerprint: c8b328d5d2241833249df78e198cc72eebc38bf733d4beb50d190fb371a20d52
    status: Archived
    audit_ids:
    - audit-b8bec3b781cd
    applied: true
    created_at: '2026-08-05T19:58:14.458459+00:00'
    applied_at: '2026-08-05T19:58:23.680139+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b8bec3b781cd
    project_id: proj-14849f1b
    task_id: OOMPAH-547
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c8b328d5d2241833249df78e198cc72eebc38bf733d4beb50d190fb371a20d52
    attempts:
    - version: 1
      attempt_id: attempt-bf8b6e697d8d
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c8b328d5d2241833249df78e198cc72eebc38bf733d4beb50d190fb371a20d52
      created_at: '2026-08-05T19:29:29.140327+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T19:29:29.140327+00:00'
      branch_key: OOMPAH-547
      failure_classification: policy_incompatibility
      ended_at: '2026-08-05T19:41:00.478829+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-05T19:41:10.478799+00:00'
    - version: 1
      attempt_id: attempt-4f67416d79d3
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c8b328d5d2241833249df78e198cc72eebc38bf733d4beb50d190fb371a20d52
      created_at: '2026-08-05T19:41:31.886033+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-05T19:41:31.886033+00:00'
      branch_key: OOMPAH-547
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-08-05T19:58:14.458231+00:00'
      ended_at: '2026-08-05T19:58:14.458231+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T19:24:20.053853+00:00'
    updated_at: '2026-08-05T19:58:14.458231+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-bf8b6e697d8d
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c8b328d5d2241833249df78e198cc72eebc38bf733d4beb50d190fb371a20d52
    created_at: '2026-08-05T19:29:29.140327+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T19:29:29.140327+00:00'
    branch_key: OOMPAH-547
    failure_classification: policy_incompatibility
    ended_at: '2026-08-05T19:41:00.478829+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-05T19:41:10.478799+00:00'
  - version: 1
    attempt_id: attempt-4f67416d79d3
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c8b328d5d2241833249df78e198cc72eebc38bf733d4beb50d190fb371a20d52
    created_at: '2026-08-05T19:41:31.886033+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-05T19:41:31.886033+00:00'
    branch_key: OOMPAH-547
    candidate_rotation_count: 1
oompah.task_costs:
  total_input_tokens: 57
  total_output_tokens: 1975
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 57
      output_tokens: 1975
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 57
    output_tokens: 1975
    cost_usd: 0.0
    recorded_at: '2026-08-05T19:40:57.093997+00:00'
---
## Summary

Reinterpret Issue.blocked_by and existing dependency APIs as finish-order constraints. Add start_blocked_by metadata plus supported CLI/API add/remove operations for hard-start dependencies. Normal finish dependencies must not reject implementation dispatch; hard-start edges must reject until satisfied. Inherit both relationship types from parent epics at the appropriate dispatch or integration boundary. Validate new edges against cycles across the combined graph and return an actionable edge path.

Tests must cover ordinary dispatch, inherited epic edges, P0 behavior, duplicate preflight, cycle creation/rejection, exact idempotent removal, native/GitHub/GitLab persistence, and API/CLI errors.

Acceptance criteria: finish edges allow early work, hard-start edges preserve true prerequisites, cycles cannot be introduced, existing dependency data remains readable, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:23
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
author: oompah
created: 2026-07-29 17:57
---
Implementation is complete on epic-OOMPAH-545. Full project gate passed: 13,213 tests passed, 7 skipped. Final rebase, merge, and deployment are in progress; this task remains human-owned and must not be dispatched.
---
author: oompah
created: 2026-07-29 18:15
---
The parent epic OOMPAH-545 merged from epic-OOMPAH-545, but this task was Backlog with work branch unset. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-29 18:17
---
The parent epic OOMPAH-545 merged from epic-OOMPAH-545, but this task was Needs Human with work branch unset. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-29 18:27
---
Implemented in PR #579 and merged to main at 31f8938b8f669a316a830690aaedcc1e0d3834bf. Full GitHub CI passed on Python 3.11, 3.12, and 3.13; focused post-rebase compatibility tests passed.
---
author: oompah
created: 2026-08-05 19:24
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-05 19:29
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 19:29
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 19:40
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 34
- Tokens: 57 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 11m 13s
- Log: OOMPAH-547__20260805T192953Z.jsonl
---
author: oompah
created: 2026-08-05 19:41
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
author: oompah
created: 2026-08-05 19:41
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-05 19:41
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 19:58
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merged_sha: 31f8938b8f669a316a830690aaedcc1e0d3834bf
- current_head: da53569a99412c0c8bf2e45f1c0587837a36b444
- merge_pr: #579
- test_dependency_graph: 3/3 passed
- test_p0_dispatch_bypass: 13/13 passed
- test_server_dependencies: 27/27 passed
- test_task_cli_dependency_subset: 10/10 passed
- test_github_tracker_dependency_subset: 8/8 passed
- test_gitlab_tracker_dependency_subset: 4/4 passed
- test_parallel_epic_children: 34/34 passed
- test_coordination: 15/15 passed
- test_worker_submission: 14/14 passed
---
<!-- COMMENTS:END -->
