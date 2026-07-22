---
id: OOMPAH-406
type: bug
status: Done
priority: 2
title: '[backend:orchestrator] Dispatch loop stall diagnostics follow (all thread
  stacks)'
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-22T08:36:35.680434Z'
updated_at: '2026-07-22T15:55:48.482987Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#535
  owner: lesserevil
  repo: oompah
  number: '535'
  url: https://github.com/lesserevil/oompah/issues/535
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-22T15:44:54.813036+00:00'
oompah.intake:
  missing_fields: []
  scope: small
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: pass
  last_validated_at: '2026-07-22T08:37:52.327186+00:00'
oompah.agent_run_id: 227e482a-6852-4114-a48b-e9a623582e0f
oompah.task_costs:
  total_input_tokens: 823393
  total_output_tokens: 5277
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 823393
      output_tokens: 5277
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 823383
    output_tokens: 3616
    cost_usd: 0.0
    recorded_at: '2026-07-22T15:50:19.355724+00:00'
  - profile: deep
    model: unknown
    input_tokens: 10
    output_tokens: 1661
    cost_usd: 0.0
    recorded_at: '2026-07-22T15:55:42.153475+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:orchestrator`:

> Dispatch loop stall diagnostics follow (all thread stacks)

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Dispatch loop stall diagnostics follow (all thread stacks)

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: d6ccea1ca2125802
- dedup_fingerprint: d6ccea1ca2125802
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/535
- Requestor: @NVShawn
- Reference: lesserevil/oompah#535

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 15:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 15:34
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 15:34
---
Understanding: Investigating OOMPAH-406 as Duplicate Investigator. The issue is an auto-filed error from backend:orchestrator about 'Dispatch loop stall diagnostics follow (all thread stacks)'. I will search existing tasks for duplicates before any implementation work.
---
author: oompah
created: 2026-07-22 15:37
---
Discovery: Duplicate screening complete — NO duplicate found.

Searched across all .oompah/tasks/ directories (open, archived, merged, done, backlog), docs, plans, README.md, and WORKFLOW.md for:
- 'Dispatch loop stall', 'stall diagnostics', 'thread stacks'
- fingerprint d6ccea1ca2125802
- 'backend:orchestrator' errors
- related terms: 'dispatch loop', 'orchestrator error', 'stall'

Findings:
1. No task in any state matches the fingerprint d6ccea1ca2125802.
2. No task describes the 'Dispatch loop stall diagnostics follow (all thread stacks)' error.
3. The closest related tasks are OOMPAH-58/OOMPAH-93/OOMPAH-97 etc. which cover a DIFFERENT error pattern: 'backend:webhooks / WebhookForwarder: disabling webhook forwarding' with fingerprint fab624f77cb2c7ae — a different component and a different error.
4. Source code confirmed: the error is logged at oompah/orchestrator.py:2591 in _dump_stale_dispatch_threads() when the dispatch loop is first declared stale. It uses logger.error() which causes error_watcher to auto-file it.

This is a unique, previously-unreported error pattern. No implementation done — handing off to the appropriate focus.
---
author: oompah
created: 2026-07-22 15:40
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 15:40
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-22 15:50
---
Agent completed successfully in 598s (826999 tokens)
---
author: oompah
created: 2026-07-22 15:50
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 14
- Tokens: 823.4K in / 3.6K out [827.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 58s
- Log: OOMPAH-406__20260722T154415Z.jsonl
---
author: oompah
created: 2026-07-22 15:50
---
Agent completed without closing this issue (598s (826999 tokens)). Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 15:50
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-22 15:50
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-22 15:55
---
Understanding (continuation): Previous agent (Run #1) already implemented the fix and pushed it to origin/OOMPAH-406. This run verifies the work and closes the task.

Root cause: In oompah/orchestrator.py, _dump_stale_dispatch_threads() used logger.error() to introduce the diagnostic thread dump. This caused error_watcher to auto-file a new bug task on every dispatch loop stall, creating noise.

Fix: Changed logger.error() → logger.warning() at line 2591. The stale-loop alert and recovery path already make the situation operator-visible; the thread dump line is just a diagnostic header, not a new failure.

Test: Added test_thread_dump_marker_is_warning_not_error to tests/test_dispatch_loop_heartbeat.py — confirms the log record is at WARNING (not ERROR) level.

Verification: All 11708 tests pass (make test). Specific new test passes in isolation.
---
author: oompah
created: 2026-07-22 15:55
---
Fixed: changed logger.error() to logger.warning() in _dump_stale_dispatch_threads() (oompah/orchestrator.py:2591) so dispatch-loop thread dump diagnostics no longer trigger error_watcher. Added regression test test_thread_dump_marker_is_warning_not_error. All 11708 tests pass.
---
author: oompah
created: 2026-07-22 15:55
---
Agent completed successfully in 300s (1671 tokens)
---
author: oompah
created: 2026-07-22 15:55
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 20, Tool calls: 9
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 0s
- Log: OOMPAH-406__20260722T155045Z.jsonl
---
author: oompah
created: 2026-07-22 15:55
---
Review handoff deferred: the task branch has unmerged work, but this project is at its open review limit.

Branch: `OOMPAH-406`
Target branch: `main`
Unmerged commits: 1 commit
Open reviews: 2/1

oompah will create the review automatically when review capacity is available.

Recent commits:
  a3905b880 OOMPAH-406: avoid filing thread dump diagnostics as errors
---
<!-- COMMENTS:END -->
