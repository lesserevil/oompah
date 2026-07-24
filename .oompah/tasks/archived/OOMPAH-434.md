---
id: OOMPAH-434
type: bug
status: Archived
priority: 2
title: "[backend:orchestrator] Dispatch loop stale but 2 agent(s) are active \u2014\
  \ skipping auto-restart to avoid killing in-flight work. Restart manually when agents\
  \ complete."
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-23T23:05:43.083575Z'
updated_at: '2026-07-24T01:32:01.445261Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#548
  owner: lesserevil
  repo: oompah
  number: '548'
  url: https://github.com/lesserevil/oompah/issues/548
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Open
  last_synced_at: '2026-07-24T00:51:06.685185+00:00'
  last_github_state: closed
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
  last_validated_at: '2026-07-23T23:05:49.654022+00:00'
oompah.agent_run_id: e8e31b13-bbf6-4c54-908e-5ca517f38736
oompah.task_costs:
  total_input_tokens: 14
  total_output_tokens: 3854
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 14
      output_tokens: 3854
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 14
    output_tokens: 3854
    cost_usd: 0.0
    recorded_at: '2026-07-24T01:24:02.174481+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:orchestrator`:

> Dispatch loop stale but 2 agent(s) are active — skipping auto-restart to avoid killing in-flight work. Restart manually when agents complete.

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Dispatch loop stale but 2 agent(s) are active — skipping auto-restart to avoid killing in-flight work. Restart manually when agents complete.

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 554dbfb5f815ad48
- dedup_fingerprint: 554dbfb5f815ad48
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/548
- Requestor: @NVShawn
- Reference: lesserevil/oompah#548

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-24 01:22
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-24 01:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-24 01:22
---
Understanding: Investigating OOMPAH-434 as Duplicate Investigator. The issue reports an error message 'Dispatch loop stale but 2 agent(s) are active — skipping auto-restart to avoid killing in-flight work. Restart manually when agents complete.' auto-filed by error_watcher. My role is to determine if this is a duplicate of an existing task before any implementation work begins. Searching task history for similar dispatch loop staleness errors now.
---
author: oompah
created: 2026-07-24 01:23
---
Discovery: OOMPAH-434 is a confirmed duplicate of OOMPAH-432.

**Root cause:** Both issues report the same error from `recover_stale_dispatch_loop()` in `oompah/orchestrator.py`. The method called `logger.error()` when the dispatch loop was stale but active agents prevented auto-restart, causing `error_watcher` to auto-file a bug task.

**Why dedup missed it:** OOMPAH-432 reported '4 agent(s) are active'; OOMPAH-434 reports '2 agent(s) are active'. The agent count is embedded in the log message, producing a different fingerprint (`ac6326253c85b77b` vs `554dbfb5f815ad48`), which bypassed the dedup guard.

**Fix status:** OOMPAH-432 was **already Merged** (PR #551, 2026-07-24 01:17). The fix is present in the codebase — `oompah/orchestrator.py` lines 2552–2557 already use `logger.warning()` with a comment explaining the rationale. A regression test `test_skips_restart_logs_warning_not_error_with_active_agents` was added in `tests/test_dispatch_loop_heartbeat.py`.

**Action:** Archiving OOMPAH-434 as duplicate-of:OOMPAH-432. No further implementation needed.
---
author: oompah
created: 2026-07-24 01:23
---
duplicate-of:OOMPAH-432
---
author: oompah
created: 2026-07-24 01:24
---
Agent completed successfully in 112s (3868 tokens)
---
author: oompah
created: 2026-07-24 01:24
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 26, Tool calls: 16
- Tokens: 14 in / 3.9K out [3.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 52s
- Log: OOMPAH-434__20260724T012225Z.jsonl
---
<!-- COMMENTS:END -->
