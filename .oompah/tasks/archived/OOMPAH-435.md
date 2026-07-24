---
id: OOMPAH-435
type: bug
status: Archived
priority: 2
title: "[backend:orchestrator] Dispatch loop stale but 1 agent(s) are active \u2014\
  \ skipping auto-restart to avoid killing in-flight work. Restart manually when agents\
  \ complete."
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-23T23:37:21.005014Z'
updated_at: '2026-07-24T01:32:04.570624Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#550
  owner: lesserevil
  repo: oompah
  number: '550'
  url: https://github.com/lesserevil/oompah/issues/550
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Open
  last_synced_at: '2026-07-24T00:51:08.001379+00:00'
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
  last_validated_at: '2026-07-23T23:37:22.365662+00:00'
oompah.agent_run_id: e374caab-e323-4740-a13f-e06ee4fa55a0
---
## Summary

### Problem

Oompah detected a backend error from `backend:orchestrator`:

> Dispatch loop stale but 1 agent(s) are active — skipping auto-restart to avoid killing in-flight work. Restart manually when agents complete.

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Dispatch loop stale but 1 agent(s) are active — skipping auto-restart to avoid killing in-flight work. Restart manually when agents complete.

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 66d86d4396709bc2
- dedup_fingerprint: 66d86d4396709bc2
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/550
- Requestor: @NVShawn
- Reference: lesserevil/oompah#550

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-24 01:24
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-24 01:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-24 01:24
---
Understanding: Screening this auto-filed backend:orchestrator stale-dispatch warning for duplicates. I will search existing tasks by the exact message and related dispatch-loop/active-agent terms, then read each plausible candidate's full description and comments before deciding whether to archive this task or hand it off for implementation.
---
author: oompah
created: 2026-07-24 01:25
---
Discovery: Confirmed duplicate of OOMPAH-432 (https://github.com/lesserevil/oompah/issues/546). OOMPAH-432 reports the identical backend:orchestrator message and code path; only the runtime agent count differs (4 versus 1), which explains the different error_watcher fingerprint. Its full comments identify recover_stale_dispatch_loop() as the source, and merged commit 72561463b changed that active-agent branch from logger.error to logger.warning and added a regression proving ErrorWatcher does not create an issue. OOMPAH-435 was filed shortly after the original ERROR occurrence, so no separate implementation is needed.
---
author: oompah
created: 2026-07-24 01:26
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 0, Tool calls: 11
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 36s
- Log: OOMPAH-435__20260724T012425Z.jsonl
---
author: oompah
created: 2026-07-24 01:26
---
duplicate-of:OOMPAH-432
---
<!-- COMMENTS:END -->
