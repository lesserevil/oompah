---
id: OOMPAH-433
type: bug
status: In Progress
priority: 2
title: "[backend:orchestrator] Dispatch loop stale but 3 agent(s) are active \u2014\
  \ skipping auto-restart to avoid killing in-flight work. Restart manually when agents\
  \ complete."
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-23T22:58:16.587989Z'
updated_at: '2026-07-24T01:13:22.277252Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#547
  owner: lesserevil
  repo: oompah
  number: '547'
  url: https://github.com/lesserevil/oompah/issues/547
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-24T01:13:19.516620+00:00'
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
  last_validated_at: '2026-07-23T22:58:23.463584+00:00'
oompah.agent_run_id: a88edbec-3040-4bc7-acb9-782c0068c38a
oompah.task_costs:
  total_input_tokens: 1078648
  total_output_tokens: 4750
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1078648
      output_tokens: 4750
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 1078648
    output_tokens: 4750
    cost_usd: 0.0
    recorded_at: '2026-07-24T01:12:39.705954+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:orchestrator`:

> Dispatch loop stale but 3 agent(s) are active — skipping auto-restart to avoid killing in-flight work. Restart manually when agents complete.

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Dispatch loop stale but 3 agent(s) are active — skipping auto-restart to avoid killing in-flight work. Restart manually when agents complete.

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: d26b340507ad3c3b
- dedup_fingerprint: d26b340507ad3c3b
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/547
- Requestor: @NVShawn
- Reference: lesserevil/oompah#547

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-24 01:08
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-24 01:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-24 01:08
---
Understanding: duplicate-screening only. I will search native tasks and project docs for the exact stale dispatch-loop warning and related orchestrator watchdog behavior, then read each plausible candidate's full description/comments before deciding whether this task is a confirmed duplicate or needs implementation handoff.
---
author: oompah
created: 2026-07-24 01:12
---
Discovery: no clear duplicate confirmed. Exact message/fingerprint d26b340507ad3c3b has no prior task. Full records reviewed: OOMPAH-406 changed the stale thread-dump header from ERROR to WARNING; OOMPAH-407 changed the initial stale-alert arm from ERROR to WARNING; OOMPAH-415 changed stale threshold/grace timing; OOMPAH-414 explicitly identifies 406/407 as logging-noise fixes. Current source is a third, unchanged logger.error in recover_stale_dispatch_loop() when running_count > 0 (oompah/orchestrator.py:2544-2556), introduced by the original heartbeat feature. It is the same subsystem but a distinct unhandled branch not resolved or tested by the reviewed tasks.
---
author: oompah
created: 2026-07-24 01:12
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate found. OOMPAH-433 is a related follow-on to OOMPAH-406/OOMPAH-407, not scope already covered by either merged task.
2. Evidence: searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for the exact message, fingerprint, stale-loop recovery, and active-agent restart guard. Read full canonical records for OOMPAH-406, OOMPAH-407, OOMPAH-414, OOMPAH-415, and OOMPAH-256. OOMPAH-406 handles _dump_stale_dispatch_threads(); OOMPAH-407 handles _arm_dispatch_stale_alert(); OOMPAH-415 handles threshold/grace timing. The current ERROR remains at oompah/orchestrator.py:2550 in recover_stale_dispatch_loop() when active agents prevent restart. tests/test_dispatch_loop_heartbeat.py::test_skips_restart_when_agents_are_running verifies restart suppression but not log severity or ErrorWatcher behavior.
3. Remaining work/risks: implement graceful logging for this expected safety branch while preserving dashboard/operator visibility and the no-kill behavior; add a regression test using ErrorWatcher, analogous to OOMPAH-407's test, and verify unrelated ERROR records still file normally. Run the relevant heartbeat/error-watcher tests and make test.
4. Recommended next focus: feature (backend bug implementation). No source changes were made during duplicate screening.
---
author: oompah
created: 2026-07-24 01:12
---
Agent completed successfully in 249s (1083398 tokens)
---
author: oompah
created: 2026-07-24 01:12
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 23
- Tokens: 1.1M in / 4.8K out [1.1M total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 9s
- Log: OOMPAH-433__20260724T010837Z.jsonl
---
author: oompah
created: 2026-07-24 01:12
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-24 01:12
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-24 01:12
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-24 01:13
---
Understanding: The active-agent branch of stale dispatch-loop recovery is an expected safety deferral, but it is logged at ERROR and therefore auto-filed by error_watcher. I will inspect the recovery and watcher contracts, downgrade/handle only this expected branch while retaining an actionable operator message, add regression coverage including preservation of genuine error reporting, run Makefile quality gates, then commit and push.
---
<!-- COMMENTS:END -->
