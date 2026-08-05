---
id: OOMPAH-546
type: feature
status: Archived
priority: 0
title: Add Ready to Integrate lifecycle and integration metadata
parent: OOMPAH-545
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:08.114469Z'
updated_at: '2026-08-05T19:39:22.543951Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-d93896d8e3ef: '2026-08-05T19:38:14.706256+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-546
    target_state: Archived
    evidence_fingerprint: da1be0232d1ddfe4d875ae9bde769f55d3f8145c97b6d70d7406286519e417c0
    audit_ids:
    - audit-f25e7a0cb9cd
    kind: result
    applied: true
    retired_at: '2026-08-05T19:38:14.706267+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-546
    audit_id: audit-f25e7a0cb9cd
    attempt_id: attempt-d93896d8e3ef
    target_state: Archived
    evidence_fingerprint: da1be0232d1ddfe4d875ae9bde769f55d3f8145c97b6d70d7406286519e417c0
    status: Archived
    audit_ids:
    - audit-f25e7a0cb9cd
    applied: true
    created_at: '2026-08-05T19:38:14.706284+00:00'
    applied_at: '2026-08-05T19:38:24.302924+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f25e7a0cb9cd
    project_id: proj-14849f1b
    task_id: OOMPAH-546
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: da1be0232d1ddfe4d875ae9bde769f55d3f8145c97b6d70d7406286519e417c0
    attempts:
    - version: 1
      attempt_id: attempt-d93896d8e3ef
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: da1be0232d1ddfe4d875ae9bde769f55d3f8145c97b6d70d7406286519e417c0
      created_at: '2026-08-05T19:26:20.885977+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T19:26:20.885977+00:00'
      branch_key: OOMPAH-546
      verdict: pass
      completed_at: '2026-08-05T19:38:14.706068+00:00'
      ended_at: '2026-08-05T19:38:14.706068+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T19:24:09.635285+00:00'
    updated_at: '2026-08-05T19:38:14.706068+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-d93896d8e3ef
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: da1be0232d1ddfe4d875ae9bde769f55d3f8145c97b6d70d7406286519e417c0
    created_at: '2026-08-05T19:26:20.885977+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T19:26:20.885977+00:00'
    branch_key: OOMPAH-546
oompah.task_costs:
  total_input_tokens: 48
  total_output_tokens: 1412
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 48
      output_tokens: 1412
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 48
    output_tokens: 1412
    cost_usd: 0.0
    recorded_at: '2026-08-05T19:39:19.878747+00:00'
---
## Summary

Implement the canonical nonterminal Ready to Integrate status and a versioned oompah.integration metadata record containing task branch, base/head/integrated SHAs, queue state, attempts, timestamps, and last error. Update canonical status aliases, dispatch/review/rollup sets, native Markdown/GitHub/GitLab normalization and metadata persistence, state/task APIs, labels, and dashboard columns. Ready tasks must not dispatch or be treated as orphaned In Progress work.

Tests must cover canonicalization, tracker round trips, epic rollup, board/detail responses, watchdog behavior, label bootstrap, and backward compatibility for tasks without metadata.

Acceptance criteria: the status and metadata survive every tracker adapter and restart, are visible in APIs/UI, do not trigger workers, and all focused tests plus make test pass.

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
created: 2026-07-29 16:25
---
Interactive owner session started implementation on the lifecycle and metadata foundation.
---
author: oompah
created: 2026-07-29 17:57
---
Implementation is complete on epic-OOMPAH-545. Full project gate passed: 13,213 tests passed, 7 skipped. Final rebase, merge, and deployment are in progress; this task remains human-owned and must not be dispatched.
---
author: oompah
created: 2026-07-29 18:15
---
The parent epic OOMPAH-545 merged from epic-OOMPAH-545, but this task was Open with work branch unset. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
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
created: 2026-08-05 19:26
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 19:26
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 19:38
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 31f8938b8f669a316a830690aaedcc1e0d3834bf
- merge_pr: #579 epic-OOMPAH-545 -> main
- status_defined_at: oompah/statuses.py:18 READY_TO_INTEGRATE = "Ready to Integrate"
- status_aliases: ready to integrate, ready-to-integrate, ready for integration
- integration_record_version: 2 (oompah/integration.py INTEGRATION_RECORD_VERSION)
- integration_states: working, ready, queued, integrating, blocked, integrated, needs_human
- focused_tests_present: tests/test_statuses.py, tests/test_integration_record.py, tests/test_oompah_md_tracker.py, tests/test_orchestrator_merged.py, tests/test_standalone_ready_to_integrate.py, tests/test_submission_fencing.py, tests/test_integration_executor.py, tests/test_delivery_plane_recovery.py, tests/test_quality_gate.py
- current_head: b53bdbc77c7a50d332a97096ebc85d7923280854
- workspace_clean: true
---
author: oompah
created: 2026-08-05 19:39
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 28
- Tokens: 48 in / 1.4K out [1.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 12m 43s
- Log: OOMPAH-546__20260805T192653Z.jsonl
---
<!-- COMMENTS:END -->
