---
id: OOMPAH-398
type: task
status: In Review
priority: 1
title: Add configurable stalled-task remediation watchdog
parent: null
children: []
blocked_by: []
labels:
- reliability
- watchdog
assignee: null
created_at: '2026-07-22T03:59:50.765371Z'
updated_at: '2026-07-22T04:21:58.280600Z'
work_branch: OOMPAH-398
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/529
review_number: '529'
merged_at: null
oompah.agent_run_id: 9ea85cd9-5b86-44da-aa94-411cfb9adeb1
oompah.task_costs:
  total_input_tokens: 510200
  total_output_tokens: 33663
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 510200
      output_tokens: 33663
      cost_usd: 0.0
  runs:
  - profile: standard
    model: unknown
    input_tokens: 191477
    output_tokens: 1295
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:01:19.313691+00:00'
  - profile: deep
    model: unknown
    input_tokens: 157790
    output_tokens: 1341
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:02:27.911352+00:00'
  - profile: standard
    model: unknown
    input_tokens: 51
    output_tokens: 29942
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:20:14.733944+00:00'
  - profile: standard
    model: unknown
    input_tokens: 160882
    output_tokens: 1085
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:20:57.479284+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/529
oompah.review_number: '529'
oompah.work_branch: OOMPAH-398
oompah.target_branch: main
---
## Summary

Implement a scheduler-owned watchdog that periodically audits stalled task states and resolves them when the evidence supports a safe automated action. The schedule must be configurable through OOMPAH_STALLED_TASK_WATCHDOG_INTERVAL_SECONDS, defaulting to 1800 seconds (30 minutes); configuration belongs in .env/.env.example, not WORKFLOW.md.\n\nScope:\n- Audit Needs Human, Needs CI Fix, Needs Rebase, Needs Answer, and any explicit Blocked/Stalled status across all managed projects.\n- Classify each task as actionable, genuinely human-blocked, obsolete, or insufficient-evidence.\n- Perform only safe, evidence-backed remediations: reopen a task whose prior focus completed without a human question; archive an obsolete alert whose referenced CI/PR has succeeded or been superseded; transition a task to the appropriate automated repair state when a known retry/remediation path applies.\n- Never auto-close/archive a task with unresolved current CI failure, a pending user question, or ambiguous external state.\n- Record the evidence, decision, and action in an oompah-authored task comment and structured watchdog telemetry.\n- Surface audit counts, last-run time, action count, and skipped/manual-review reasons in the API/dashboard maintenance snapshot.\n\nTests:\n- Unit tests for schedule/default/env parsing and every classification outcome.\n- Fake tracker/SCM tests for safe reopen, safe archive, and refusal when evidence is ambiguous or CI is still failing.\n- Integration test that the watchdog is coalesced, respects its configured interval, and does not block normal dispatch.\n- Run make test.\n\nAcceptance criteria:\n- Default schedule is 30 minutes and can be changed only with the documented environment setting.\n- Every stalled state is evaluated without creating duplicate actions across repeated runs.\n- Automated changes are explainable from task comments and API telemetry.\n- Genuine human blockers remain untouched and visible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 04:00
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 04:00
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-22 04:01
---
Agent completed successfully in 43s (192772 tokens)
---
author: oompah
created: 2026-07-22 04:01
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 191.5K in / 1.3K out [192.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 43s
- Log: OOMPAH-398__20260722T040039Z.jsonl
---
author: oompah
created: 2026-07-22 04:01
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-398`. Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 04:01
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-22 04:01
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-22 04:02
---
Agent completed successfully in 47s (159131 tokens)
---
author: oompah
created: 2026-07-22 04:02
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 4
- Tokens: 157.8K in / 1.3K out [159.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 47s
- Log: OOMPAH-398__20260722T040151Z.jsonl
---
author: oompah
created: 2026-07-22 04:02
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-398`. No stronger profile is configured; retrying with 'deep' in 20s (2/3).
---
author: oompah
created: 2026-07-22 04:03
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 04:03
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-22 04:05
---
Understanding: Previous CI Fixer agents made no commits. This is a full feature implementation task requiring: (1) new oompah/stalled_task_watchdog.py module with classification logic for NEEDS_HUMAN/NEEDS_CI_FIX/NEEDS_REBASE/NEEDS_ANSWER states; (2) config field OOMPAH_STALLED_TASK_WATCHDOG_INTERVAL_SECONDS (default 1800) in config.py and .env.example; (3) orchestrator integration via _run_maintenance_job in _run_step5b_maintenance; (4) telemetry in _maintenance_status; (5) tests. My approach: implement a pure classification+remediation module following the yolo_watchdog.py pattern, wire it into the maintenance lane, add comprehensive tests.
---
author: oompah
created: 2026-07-22 04:15
---
Implementation complete. Added: (1) oompah/stalled_task_watchdog.py — pure classification+remediation module auditing NEEDS_HUMAN, NEEDS_CI_FIX, NEEDS_REBASE, NEEDS_ANSWER states; (2) config.stalled_task_watchdog_interval_seconds (default 1800) in config.py with OOMPAH_STALLED_TASK_WATCHDOG_INTERVAL_SECONDS env var; (3) .env.example entry; (4) _maybe_run_stalled_task_watchdog() + _do_stalled_task_watchdog() wired into _run_step5b_maintenance in orchestrator.py; (5) tests/test_stalled_task_watchdog.py with 74 tests. All 11338 tests pass.
---
author: oompah
created: 2026-07-22 04:19
---
Completion: Stalled-task remediation watchdog implemented and pushed to origin/OOMPAH-398.

Delivered:
- oompah/stalled_task_watchdog.py: pure classifier auditing NEEDS_HUMAN, NEEDS_CI_FIX, NEEDS_REBASE, NEEDS_ANSWER, and custom Blocked/Stalled states; safe remediations (reopen when accidental stall, CI evidence, conflict resolved); idempotency via sentinel comments; telemetry via WatchdogAuditResult.to_dict()
- config.py: stalled_task_watchdog_interval_seconds=1800, OOMPAH_STALLED_TASK_WATCHDOG_INTERVAL_SECONDS env var, 60 s minimum clamp
- orchestrator.py: _maybe_run_stalled_task_watchdog() + _do_stalled_task_watchdog() wired into _run_step5b_maintenance(); telemetry in _maintenance_status
- .env.example: OOMPAH_STALLED_TASK_WATCHDOG_INTERVAL_SECONDS documented
- tests/test_stalled_task_watchdog.py: 74 tests; all 11338 project tests pass

Acceptance criteria verified: default 30-minute interval configurable only via env var; no duplicate actions across runs; automated changes explained via comments and maintenance snapshot; genuine human blockers left untouched.
---
author: oompah
created: 2026-07-22 04:20
---
Implemented configurable stalled-task remediation watchdog: new oompah/stalled_task_watchdog.py module with classify_stalled_task()/run_watchdog_audit() pure APIs; OOMPAH_STALLED_TASK_WATCHDOG_INTERVAL_SECONDS config (default 1800s); orchestrator integration via _run_step5b_maintenance maintenance lane; 74 new tests; all 11338 project tests passing.
---
author: oompah
created: 2026-07-22 04:20
---
Agent completed successfully in 1003s (29993 tokens)
---
author: oompah
created: 2026-07-22 04:20
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 89, Tool calls: 62
- Tokens: 51 in / 29.9K out [30.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 16m 43s
- Log: OOMPAH-398__20260722T040334Z.jsonl
---
author: oompah
created: 2026-07-22 04:20
---
Close refused by orchestrator: branch `OOMPAH-398` has 1 commit not on `main` and no open PR targets `main` from this branch.

Diagnostic:
  Unmerged commits: 1
    c9678a997 OOMPAH-398: Add configurable stalled-task remediation watchdog
  Open PRs from this branch: 0
  Merged PRs from this branch: 0

Required: open a PR before closing.
  gh pr create --base main --head OOMPAH-398 --title "OOMPAH-398: Add configurable stalled-task remediation watchdog" --body "..."

Task reopened. Re-dispatch on the next tick will see this comment in its prompt context.
---
author: oompah
created: 2026-07-22 04:20
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 04:20
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-22 04:20
---
Agent completed successfully in 35s (161967 tokens)
---
author: oompah
created: 2026-07-22 04:20
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 4
- Tokens: 160.9K in / 1.1K out [162.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 35s
- Log: OOMPAH-398__20260722T042025Z.jsonl
---
author: oompah
created: 2026-07-22 04:21
---
Agent completed without closing this issue (35s (161967 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 04:21
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-22 04:21
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-22 04:21
---
Completion: PR #529 opened (https://github.com/lesserevil/oompah/pull/529) for the stalled-task remediation watchdog implementation.

Delivered in this PR:
- oompah/stalled_task_watchdog.py: pure classifier auditing Needs Human, Needs CI Fix, Needs Rebase, Needs Answer, and custom Blocked/Stalled states; safe remediations with idempotency via sentinel comments; telemetry via WatchdogAuditResult.to_dict()
- config.py: stalled_task_watchdog_interval_seconds=1800, OOMPAH_STALLED_TASK_WATCHDOG_INTERVAL_SECONDS env var, 60s minimum clamp
- orchestrator.py: _maybe_run_stalled_task_watchdog() + _do_stalled_task_watchdog() wired into _run_step5b_maintenance(); telemetry in _maintenance_status
- .env.example: OOMPAH_STALLED_TASK_WATCHDOG_INTERVAL_SECONDS documented
- tests/test_stalled_task_watchdog.py: 74 tests; all 11338 project tests passing

All acceptance criteria verified.
---
<!-- COMMENTS:END -->
