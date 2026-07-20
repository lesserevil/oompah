---
id: OOMPAH-225
type: bug
status: Archived
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-38 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-38.md and /home/shedwards/.oompah/repos/trickle/.oompah/ta...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-18T01:07:28.570449Z'
updated_at: '2026-07-18T02:05:09.626389Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#430
  owner: lesserevil
  repo: oompah
  number: '430'
  url: https://github.com/lesserevil/oompah/issues/430
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Archived
  last_synced_at: '2026-07-18T02:05:06.069718+00:00'
  last_github_state: closed
oompah.intake:
  missing_fields: []
  scope: unknown
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: pass
  last_validated_at: '2026-07-18T01:08:53.134249+00:00'
oompah.agent_run_id: e2ec445f-ab0a-4e39-931a-9831d798633b
oompah.task_costs:
  total_input_tokens: 9
  total_output_tokens: 1684
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 9
      output_tokens: 1684
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 9
    output_tokens: 1684
    cost_usd: 0.0
    recorded_at: '2026-07-18T02:00:56.285114+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-38 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-38.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-38.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-38.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-38.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-38 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-38.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-38.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-38.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-38.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 1167643b2db542ca
- dedup_fingerprint: 1167643b2db542ca
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/430
- Requestor: @NVShawn
- Reference: lesserevil/oompah#430

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 01:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 01:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 02:00
---
Understanding: Investigating whether this is a duplicate of an existing issue. The error is about duplicate native oompah task ID 'trickle-38' found in two directories (done/ and merged/) within the oompah_md_tracker backend. The error_watcher auto-filed this because the duplicate detection warning is treated as an error. Plan: search existing tasks for similar 'duplicate task ID' or 'oompah_md_tracker' errors before any implementation work.
---
author: oompah
created: 2026-07-18 02:00
---
Discovery: OOMPAH-225 is a confirmed duplicate of OOMPAH-220. Both report the exact same root cause: oompah/oompah_md_tracker.py used logger.error() to report duplicate task IDs (the code already handled them gracefully), causing error_watcher to auto-file each occurrence as a separate bug. OOMPAH-220's duplicate_detector already identified OOMPAH-225 (trickle-38) as a sibling duplicate in the same error_watcher burst. The fix (logger.error → logger.warning at oompah_md_tracker.py ~line 871) was implemented in OOMPAH-220. Archiving OOMPAH-225 as duplicate-of:OOMPAH-220.
---
author: oompah
created: 2026-07-18 02:00
---
duplicate-of:OOMPAH-220
---
author: oompah
created: 2026-07-18 02:00
---
Agent completed successfully in 74s (1693 tokens)
---
author: oompah
created: 2026-07-18 02:00
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 11, Tool calls: 6
- Tokens: 9 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 14s
- Log: OOMPAH-225__20260718T015949Z.jsonl
---
<!-- COMMENTS:END -->
