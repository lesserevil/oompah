---
id: OOMPAH-221
type: bug
status: Archived
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-31 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-31.md and /home/shedwards/.oompah/repos/trickle/.oompah/ta...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-18T01:07:07.852089Z'
updated_at: '2026-07-18T01:14:58.983397Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#426
  owner: lesserevil
  repo: oompah
  number: '426'
  url: https://github.com/lesserevil/oompah/issues/426
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Archived
  last_synced_at: '2026-07-18T01:14:56.894613+00:00'
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
  last_validated_at: '2026-07-18T01:08:24.005423+00:00'
oompah.agent_run_id: 21236893-831f-4bf5-9494-386de9dcef2f
oompah.task_costs:
  total_input_tokens: 48
  total_output_tokens: 1995
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 48
      output_tokens: 1995
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 48
    output_tokens: 1995
    cost_usd: 0.0
    recorded_at: '2026-07-18T01:14:39.504949+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-31 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-31.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-31.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-31.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-31.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-31 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-31.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-31.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-31.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-31.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 4e524d1feabd1025
- dedup_fingerprint: 4e524d1feabd1025
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/426
- Requestor: @NVShawn
- Reference: lesserevil/oompah#426

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 01:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 01:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 01:11
---
Understanding: Investigating whether OOMPAH-221 is a duplicate. The issue reports that backend:oompah_md_tracker found duplicate native task ID trickle-31 in two directories (done/ and merged/), which triggered error_watcher to auto-file this task. Plan: search existing tasks for duplicate detection of this same error pattern before deciding whether to archive or hand off for implementation.
---
author: oompah
created: 2026-07-18 01:14
---
Discovery: OOMPAH-221 is a confirmed duplicate of OOMPAH-220. Both are auto-filed by error_watcher for the same underlying bug in backend:oompah_md_tracker — 'Duplicate native oompah task ID' when a task file exists in two status directories simultaneously. The descriptions, desired behavior, acceptance criteria, and steps to reproduce are word-for-word identical. The only difference is the specific trickle task ID (trickle-31 vs trickle-30) and which two directories are involved. A single code fix to oompah_md_tracker would resolve all 13 instances (OOMPAH-220 through OOMPAH-232). OOMPAH-220 was filed 5 seconds earlier and is the canonical instance. Archiving OOMPAH-221 as duplicate-of:OOMPAH-220.
---
author: oompah
created: 2026-07-18 01:14
---
duplicate-of:OOMPAH-220
---
author: oompah
created: 2026-07-18 01:14
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 35
- Tokens: 48 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 29s
- Log: OOMPAH-221__20260718T011117Z.jsonl
---
<!-- COMMENTS:END -->
