---
id: OOMPAH-548
type: feature
status: Archived
priority: 0
title: Add worker submission handoff and ordered terminal staging
parent: OOMPAH-545
children: []
blocked_by:
- OOMPAH-546
- OOMPAH-547
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:10.331989Z'
updated_at: '2026-08-05T19:56:19.310294Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-6040f00def0a: '2026-08-05T19:55:24.439893+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-548
    target_state: Archived
    evidence_fingerprint: b7a7e80267386a9b7a5075aff0dae57959cb6c636f5c05732ee536a8edf19e41
    audit_ids:
    - audit-20140d599cba
    kind: result
    applied: true
    retired_at: '2026-08-05T19:55:24.439905+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-548
    audit_id: audit-20140d599cba
    attempt_id: attempt-6040f00def0a
    target_state: Archived
    evidence_fingerprint: b7a7e80267386a9b7a5075aff0dae57959cb6c636f5c05732ee536a8edf19e41
    status: Archived
    audit_ids:
    - audit-20140d599cba
    applied: true
    created_at: '2026-08-05T19:55:24.439923+00:00'
    applied_at: '2026-08-05T19:55:32.385745+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-20140d599cba
    project_id: proj-14849f1b
    task_id: OOMPAH-548
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b7a7e80267386a9b7a5075aff0dae57959cb6c636f5c05732ee536a8edf19e41
    attempts:
    - version: 1
      attempt_id: attempt-6040f00def0a
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b7a7e80267386a9b7a5075aff0dae57959cb6c636f5c05732ee536a8edf19e41
      created_at: '2026-08-05T19:47:42.350287+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T19:47:42.350287+00:00'
      branch_key: OOMPAH-548
      verdict: pass
      completed_at: '2026-08-05T19:55:24.439708+00:00'
      ended_at: '2026-08-05T19:55:24.439708+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T19:24:29.296582+00:00'
    updated_at: '2026-08-05T19:55:24.439708+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-6040f00def0a
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b7a7e80267386a9b7a5075aff0dae57959cb6c636f5c05732ee536a8edf19e41
    created_at: '2026-08-05T19:47:42.350287+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T19:47:42.350287+00:00'
    branch_key: OOMPAH-548
oompah.task_costs:
  total_input_tokens: 42
  total_output_tokens: 936
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 42
      output_tokens: 936
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 42
    output_tokens: 936
    cost_usd: 0.0
    recorded_at: '2026-08-05T19:56:15.672280+00:00'
---
## Summary

Add oompah task submit <task-id> as the worker-scoped completion operation. Validate exact task ownership, clean worktree, pushed private branch, and current remote head; record integration metadata and transition to Ready to Integrate. When parallel epic mode is enabled, convert legacy direct Done requests from child workers into submission so no terminal path bypasses integration. After successful integration, route Done through the terminal-transition coordinator and independent audit against the integrated tree.

Tests must cover CLI and task-capability authorization, clean/pushed validation, idempotent resubmission, legacy Done conversion, stale head rejection, terminal audit staging, and clear failure comments.

Acceptance criteria: workers cannot mark unintegrated child code Done, successful submission is durable and idempotent, audit evidence references the integrated commit, and focused tests plus make test pass.

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
created: 2026-08-05 19:47
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 19:47
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 19:55
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 31f8938b8f669a316a830690aaedcc1e0d3834bf
- merge_pr: #579 epic-OOMPAH-545
- implementation_commit: 0786d2ba7 Add finish-order task submission foundation
- cli_entry_point: oompah/task_cli.py:793 _cmd_submit
- server_route: /api/v1/issues/{id}/submit
- status_constant: oompah/statuses.py:18 READY_TO_INTEGRATE
- coordinator_module: oompah/terminal_transition_coordinator.py (TerminalTransitionCoordinator)
- primary_tests: tests/test_worker_submission.py (113 lines), tests/test_integration_record.py (52 lines)
- followup_tasks_touching_submission_tests: OOMPAH-669, OOMPAH-684, OOMPAH-717, OOMPAH-731, OOMPAH-758
- archive_trigger: Aged Merged auto-archive (closed 7 days ago 2026-07-29)
---
author: oompah
created: 2026-08-05 19:56
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 19
- Tokens: 42 in / 936 out [978 total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 22s
- Log: OOMPAH-548__20260805T194802Z.jsonl
---
<!-- COMMENTS:END -->
