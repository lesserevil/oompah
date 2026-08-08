---
id: OOMPAH-669
type: bug
status: Archived
priority: 1
title: Same-head task resubmission must restore Ready to Integrate lifecycle
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-07-31T21:52:16.588312Z'
updated_at: '2026-08-08T01:10:57.333596Z'
work_branch: OOMPAH-669
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/631
review_number: '631'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2fdeca993d4c091dd5af6a63ea4ddf674c7e65b46f17ae5430e199130f7db418
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T23:01:50.853075+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: OOMPAH-570, OOMPAH-574, OOMPAH-628, and OOMPAH-661\
    \ are the closest records, but all are terminal and address queue rearming, gate-cache\
    \ retries, integrated-row reflow, or stale worker retries\u2014not `_persist_worker_submission`\
    \ failing to restore the canonical lifecycle. Active tasks OOMPAH-651, OOMPAH-664\u2013\
    667, and OOMPAH-670 are unrelated."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: de234723-7746-4658-8f43-8a3a9bbf3db5
oompah.task_costs:
  total_input_tokens: 834229
  total_output_tokens: 59894
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 834156
      output_tokens: 46419
      cost_usd: 0.0
    unknown:
      input_tokens: 73
      output_tokens: 13475
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 834061
    output_tokens: 5102
    cost_usd: 0.0
    recorded_at: '2026-07-31T23:01:50.846145+00:00'
  - profile: deep
    model: opus
    input_tokens: 95
    output_tokens: 41317
    cost_usd: 0.0
    recorded_at: '2026-07-31T23:15:56.415768+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 48
    output_tokens: 7707
    cost_usd: 0.0
    recorded_at: '2026-08-01T00:51:08.116199+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 25
    output_tokens: 5768
    cost_usd: 0.0
    recorded_at: '2026-08-01T00:54:32.260789+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-669__20260731T225919Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: duplicate_detector
    source_branch: OOMPAH-669
    source_sha: d96740a6ecdca353e40ef87e94a4ee91b8828df0
    completed_at: '2026-07-31T23:01:50.885987+00:00'
  - run_id: OOMPAH-669__20260731T230221Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: opus
    focus: ci_fix
    source_branch: OOMPAH-669
    source_sha: e8761afb6029bad39bf28e82b45a6cce92ad0768
    completed_at: '2026-07-31T23:15:56.419853+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-669
  base_branch: main
  base_sha: d96740a6ecdca353e40ef87e94a4ee91b8828df0
  head_sha: e8761afb6029bad39bf28e82b45a6cce92ad0768
  submitted_at: '2026-07-31T23:15:38.976437+00:00'
  updated_at: '2026-07-31T23:16:03.095173+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/631
oompah.review_number: '631'
oompah.work_branch: OOMPAH-669
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-070d5f1365d9: '2026-08-01T00:51:00.434147+00:00'
    attempt-902ccfea1ef9: '2026-08-01T00:54:18.488814+00:00'
    attempt-27590afa7630: '2026-08-08T01:10:46.326177+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-669
    target_state: Done
    evidence_fingerprint: 8f85331e5ecbe076fd05ac3251bdf9c0b6812ea3b5e779d1abeca6fd1d242066
    audit_ids:
    - audit-958931a65e77
    kind: result
    applied: true
    retired_at: '2026-08-01T00:51:00.434156+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-669
    target_state: Merged
    evidence_fingerprint: 8f85331e5ecbe076fd05ac3251bdf9c0b6812ea3b5e779d1abeca6fd1d242066
    audit_ids:
    - audit-64e34031252c
    kind: result
    applied: true
    retired_at: '2026-08-01T00:54:18.488836+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-669
    target_state: Archived
    evidence_fingerprint: 8d192542db44e643737857aac741bb60df1135d8e7db34ada8c2b1793d418b47
    audit_ids:
    - audit-8e01e2b46bcc
    kind: result
    applied: true
    retired_at: '2026-08-08T01:10:46.326196+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-669
    audit_id: audit-958931a65e77
    attempt_id: attempt-070d5f1365d9
    target_state: Done
    evidence_fingerprint: 8f85331e5ecbe076fd05ac3251bdf9c0b6812ea3b5e779d1abeca6fd1d242066
    status: In Validation
    audit_ids:
    - audit-958931a65e77
    applied: true
    created_at: '2026-08-01T00:51:00.434168+00:00'
    applied_at: '2026-08-01T00:51:03.973091+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-669
    audit_id: audit-64e34031252c
    attempt_id: attempt-902ccfea1ef9
    target_state: Merged
    evidence_fingerprint: 8f85331e5ecbe076fd05ac3251bdf9c0b6812ea3b5e779d1abeca6fd1d242066
    status: Merged
    audit_ids:
    - audit-64e34031252c
    applied: true
    created_at: '2026-08-01T00:54:18.488859+00:00'
    applied_at: '2026-08-01T00:54:23.783782+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-669
    audit_id: audit-8e01e2b46bcc
    attempt_id: attempt-27590afa7630
    target_state: Archived
    evidence_fingerprint: 8d192542db44e643737857aac741bb60df1135d8e7db34ada8c2b1793d418b47
    status: Archived
    audit_ids:
    - audit-8e01e2b46bcc
    kind: result
    applied: true
    created_at: '2026-08-08T01:10:46.326219+00:00'
    applied_at: '2026-08-08T01:10:54.944916+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-958931a65e77
    project_id: proj-14849f1b
    task_id: OOMPAH-669
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8f85331e5ecbe076fd05ac3251bdf9c0b6812ea3b5e779d1abeca6fd1d242066
    attempts:
    - version: 1
      attempt_id: attempt-070d5f1365d9
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8f85331e5ecbe076fd05ac3251bdf9c0b6812ea3b5e779d1abeca6fd1d242066
      created_at: '2026-08-01T00:46:51.750686+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-01T00:46:51.750686+00:00'
      branch_key: OOMPAH-669
      verdict: pass
      completed_at: '2026-08-01T00:51:00.434042+00:00'
      ended_at: '2026-08-01T00:51:00.434042+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T00:45:33.065339+00:00'
    updated_at: '2026-08-01T00:51:00.434042+00:00'
  - version: 1
    audit_id: audit-64e34031252c
    project_id: proj-14849f1b
    task_id: OOMPAH-669
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8f85331e5ecbe076fd05ac3251bdf9c0b6812ea3b5e779d1abeca6fd1d242066
    attempts:
    - version: 1
      attempt_id: attempt-902ccfea1ef9
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8f85331e5ecbe076fd05ac3251bdf9c0b6812ea3b5e779d1abeca6fd1d242066
      created_at: '2026-08-01T00:51:13.915009+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-01T00:51:13.915009+00:00'
      branch_key: OOMPAH-669
      verdict: pass
      completed_at: '2026-08-01T00:54:18.488644+00:00'
      ended_at: '2026-08-01T00:54:18.488644+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T00:45:33.065339+00:00'
    updated_at: '2026-08-01T00:54:18.488644+00:00'
  - version: 1
    audit_id: audit-8e01e2b46bcc
    project_id: proj-14849f1b
    task_id: OOMPAH-669
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8d192542db44e643737857aac741bb60df1135d8e7db34ada8c2b1793d418b47
    attempts:
    - version: 1
      attempt_id: attempt-27590afa7630
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8d192542db44e643737857aac741bb60df1135d8e7db34ada8c2b1793d418b47
      created_at: '2026-08-08T00:56:59.002224+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-08T00:56:59.002224+00:00'
      branch_key: OOMPAH-669
      selected_ref: e8761afb6029bad39bf28e82b45a6cce92ad0768
      selected_sha: e8761afb6029bad39bf28e82b45a6cce92ad0768
      verdict: pass
      completed_at: '2026-08-08T01:10:46.325923+00:00'
      ended_at: '2026-08-08T01:10:46.325923+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-08T00:56:29.871429+00:00'
    selected_ref: e8761afb6029bad39bf28e82b45a6cce92ad0768
    selected_sha: e8761afb6029bad39bf28e82b45a6cce92ad0768
    updated_at: '2026-08-08T01:10:46.325923+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-070d5f1365d9
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8f85331e5ecbe076fd05ac3251bdf9c0b6812ea3b5e779d1abeca6fd1d242066
    created_at: '2026-08-01T00:46:51.750686+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-01T00:46:51.750686+00:00'
    branch_key: OOMPAH-669
  - version: 1
    attempt_id: attempt-902ccfea1ef9
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8f85331e5ecbe076fd05ac3251bdf9c0b6812ea3b5e779d1abeca6fd1d242066
    created_at: '2026-08-01T00:51:13.915009+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-01T00:51:13.915009+00:00'
    branch_key: OOMPAH-669
  - version: 1
    attempt_id: attempt-27590afa7630
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8d192542db44e643737857aac741bb60df1135d8e7db34ada8c2b1793d418b47
    created_at: '2026-08-08T00:56:59.002224+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-08T00:56:59.002224+00:00'
    branch_key: OOMPAH-669
    selected_ref: e8761afb6029bad39bf28e82b45a6cce92ad0768
    selected_sha: e8761afb6029bad39bf28e82b45a6cce92ad0768
---
## Summary

Triggered by: OOMPAH-668

Live production reproduction on OOMPAH-668 on 2026-07-31: after an exact-head delivery error, the task was moved through Needs Human/In Progress and resubmitted from its clean registered worktree at the same pushed branch/head. POST /api/v1/issues/{id}/submit returned 201 and the task CLI printed Submitted for integration, but the canonical lifecycle remained In Progress and no new submission comment was written. Root cause is _persist_worker_submission in oompah/server.py: when the existing oompah.integration object has the same task_branch/head_sha, it returns early before tracker.update_issue(... Ready to Integrate) and before recording the new summary. This strands an explicitly resubmitted task despite a success response and forces a content-identical empty commit to change the head. Implement explicit-submit idempotency so every accepted submit request atomically reconciles lifecycle to Ready to Integrate and records/rearms delivery as appropriate, while duplicate requests already in Ready/queued/integrating stay idempotent and background synchronization cannot create loops. Coordinate with the existing queue rearm behavior from OOMPAH-570 and OOMPAH-628 rather than duplicating it. Relevant files: oompah/server.py submission persistence/API, integration queue wiring, task CLI/API response contract, and focused submission/reflow tests. Required deterministic tests: same branch/head resubmitted from In Progress, Needs Human, and Needs CI Fix becomes Ready and runs exactly one fresh delivery; duplicate same-head submission already Ready does not duplicate comments/gates/leases; concurrent status-change-versus-submit has one atomic authority winner; restart preserves the rearmed state; unrelated tasks/projects stay isolated. Acceptance: a 201 submit response always corresponds to durable Ready-to-Integrate lifecycle for that accepted generation, same-head recovery never needs an empty commit, no duplicate integration loop is introduced, focused tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 22:59
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-07-31 22:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 23:01
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 19
- Tokens: 834.1K in / 5.1K out [839.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 37s
- Log: OOMPAH-669__20260731T225919Z.jsonl
---
author: oompah
created: 2026-07-31 23:02
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-31 23:02
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-31 23:09
---
Understanding: The bug is in _persist_worker_submission (oompah/server.py). When a task has an existing 'ready' integration record with matching head/branch AND its canonical tracker status was moved via other paths (In Progress / Needs Human / Needs CI Fix), _submission_record returns the same existing IntegrationRecord object. Then _persist_worker_submission's guard 'if record is existing and head/branch match' fires and returns early — WITHOUT reconciling the tracker status back to Ready to Integrate or posting the fresh submission comment. The 201 response lies about the actual lifecycle.

Plan: swap the identity-based idempotency guard for a lifecycle-based one. Fully idempotent only when (a) the durable record is truly unchanged AND (b) the canonical tracker status is already Ready to Integrate. Any other observed status must trigger tracker.update_issue(Ready to Integrate) + fresh summary comment. Metadata is rewritten only for a genuinely new record. This keeps duplicate submits at Ready/queued/integrating idempotent while making same-head recovery from other statuses correct. Queue rearm behavior from OOMPAH-628 stays as-is.

Tests to add in tests/test_worker_submission.py: same-head resubmit from In Progress / Needs Human / Needs CI Fix atomically writes status+comment; duplicate same-head submit already at Ready to Integrate is fully idempotent; queue rearm still fires; unrelated projects stay isolated.
---
author: oompah
created: 2026-07-31 23:13
---
Implementation: fixed _persist_worker_submission in oompah/server.py.

- Replaced the identity guard 'record is existing' with a lifecycle-aware guard: fully idempotent only when the durable record is unchanged AND canonical_status == READY_TO_INTEGRATE. Any other observed canonical status (In Progress, Needs Human, Needs CI Fix, ...) triggers tracker.update_issue(Ready to Integrate) + fresh summary comment so the 201 response is truthful.
- Metadata rewrite is now skipped only when reuses_existing_record=True (same head/branch + reused IntegrationRecord). This avoids identical rewrites while still reconciling lifecycle. Fresh-generation submits (new head, or first-time submit) still write metadata.
- Removed 'integrated' from _submission_record's reuse-existing set so an explicit integrated → resubmit rebuilds a fresh 'ready' record; that in turn keeps _enqueue_worker_submission's rearm_integrated=True (OOMPAH-628) firing correctly.

Added tests/test_worker_submission.py covering:
- Same-head resubmit from In Progress / Needs Human / Needs CI Fix reconciles lifecycle atomically, records the fresh summary, and rearms exactly one queue delivery (no spurious metadata write).
- Duplicate same-head submit already at Ready to Integrate is fully idempotent — zero tracker/queue writes.
- Cross-project isolation: reconciling one task does not mutate an unrelated project's queue row.

All 10 tests in test_worker_submission.py pass. Neighboring suites (integration_queue, integration_executor, task_handoff, submit_queue_concurrency, task_cli) all green.
---
author: oompah
created: 2026-07-31 23:15
---
Verification: focused test runs pass.

- tests/test_worker_submission.py: 10/10 pass (5 pre-existing + 5 new for OOMPAH-669 lifecycle reconciliation).
- Directly affected neighboring suites: tests/test_integration_queue.py, test_integration_record.py, test_integration_conflict_repair.py, test_integration_executor.py, test_task_handoff.py, test_task_cli.py, test_submit_queue_concurrency.py — 315 passed, 0 failed.

Commit e8761afb6 pushed to origin/OOMPAH-669. The complete branch gate (make test) will run once when this branch is ready for review.
---
author: oompah
created: 2026-07-31 23:15
---
Fixed _persist_worker_submission to reconcile canonical lifecycle atomically on every accepted submit. Same-head resubmit from In Progress / Needs Human / Needs CI Fix now writes tracker.status=Ready to Integrate + fresh summary comment, restoring the durable Ready-to-Integrate invariant for the accepted generation. Duplicate submits already at Ready to Integrate stay fully idempotent (no writes, no queue reset). Removed 'integrated' from _submission_record's reuse-existing set so integrated → resubmit builds a fresh 'ready' record and keeps OOMPAH-628 queue rearm firing. New tests cover the three non-ready starting statuses, the fully-idempotent duplicate case, and cross-project isolation. Focused suites (worker_submission, integration_queue, integration_record, integration_conflict_repair, integration_executor, task_handoff, task_cli, submit_queue_concurrency) all pass — 315/315.
---
author: oompah
created: 2026-07-31 23:15
---
Agent completed successfully in 822s (41412 tokens)
---
author: oompah
created: 2026-07-31 23:15
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Claude/opus]
- Turns: 118, Tool calls: 89
- Tokens: 95 in / 41.3K out [41.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 13m 42s
- Log: OOMPAH-669__20260731T230221Z.jsonl
---
author: oompah
created: 2026-08-01 00:36
---
Branch quality gate passed for `e8761afb6029bad39bf28e82b45a6cce92ad0768` using `make test` in 397.1s. Review creation may proceed.
---
author: oompah
created: 2026-08-01 00:45
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-01 00:45
---
YOLO: merged PR #631.
---
author: oompah
created: 2026-08-01 00:46
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-01 00:46
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-01 00:51
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- merge_commit: bc5f4a60780a97bf9a16fd532b00ff0a33642cc0
- implementation_commit: e8761afb6029bad39bf28e82b45a6cce92ad0768
- pr: 631
- focused_tests: 10/10 pass (test_worker_submission.py)
- neighboring_tests: 280/280 pass
- full_gate: make test passed in 397.1s for e8761afb6
- key_fix_lines: server.py:3208 (reuse set excludes integrated), 3259-3265 (reuses_existing_record guard), 3281-3295 (lifecycle reconciliation)
---
author: oompah
created: 2026-08-01 00:51
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 70, Tool calls: 49
- Tokens: 48 in / 7.7K out [7.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 15s
- Log: OOMPAH-669__20260801T004657Z.jsonl
---
author: oompah
created: 2026-08-01 00:51
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-01 00:51
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-01 00:54
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- merge_commit: bc5f4a60780a97bf9a16fd532b00ff0a33642cc0
- implementation_commit: e8761afb6029bad39bf28e82b45a6cce92ad0768
- pr: 631
- focused_tests: 10/10 pass (test_worker_submission.py)
- neighboring_tests: 291/291 pass
- full_gate: make test passed in 397.1s for e8761afb6 (branch quality gate comment)
- key_fix_lines: server.py:3208 (reuse set excludes integrated), 3265 (reuses_existing_record guard), 3281-3295 (lifecycle reconciliation to READY_TO_INTEGRATE)
---
author: oompah
created: 2026-08-01 00:54
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 51, Tool calls: 32
- Tokens: 25 in / 5.8K out [5.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 17s
- Log: OOMPAH-669__20260801T005119Z.jsonl
---
author: oompah
created: 2026-08-08 00:57
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-08 00:57
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-08 01:10
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: bc5f4a60780a97bf9a16fd532b00ff0a33642cc0
- implementation_commit: e8761afb6029bad39bf28e82b45a6cce92ad0768
- pr: 631
- focused_tests: 10/10 in test_worker_submission.py
- full_gate: 14547 passed, 7 skipped, 1 xfailed in 378.44s
- key_fixes: server.py:3265 (lifecycle-aware return), 3281-3292 (reconciliation)
- test_coverage[0]: test_same_head_resubmit_from_in_progress_restores_ready_lifecycle
- test_coverage[1]: test_same_head_resubmit_from_needs_human_restores_ready_lifecycle
- test_coverage[2]: test_same_head_resubmit_from_needs_ci_fix_restores_ready_lifecycle
- test_coverage[3]: test_duplicate_same_head_submit_already_ready_is_fully_idempotent
- test_coverage[4]: test_same_head_resubmit_does_not_leak_to_other_projects
- requirements_met[0]: 201 submit response durable Ready lifecycle
- requirements_met[1]: Same-head recovery no empty commit
- requirements_met[2]: No duplicate integration loop
- requirements_met[3]: Lifecycle reconciles In Progress/Needs Human/Needs CI Fix to Ready
- requirements_met[4]: Duplicate submits at Ready fully idempotent
---
<!-- COMMENTS:END -->
