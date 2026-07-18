---
id: OOMPAH-228
type: bug
status: Archived
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-41 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-41.md and /home/shedwards/.oompah/repos/trickle/.oompah/ta...'
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-07-18T01:07:41.804523Z'
updated_at: '2026-07-18T02:06:56.609875Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#433
  owner: lesserevil
  repo: oompah
  number: '433'
  url: https://github.com/lesserevil/oompah/issues/433
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-18T02:05:30.601961+00:00'
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
  last_validated_at: '2026-07-18T01:09:18.660867+00:00'
oompah.agent_run_id: 2cf63b08-d7b1-45ac-8b19-0ecb2c807339
oompah.task_costs:
  total_input_tokens: 39
  total_output_tokens: 1104
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 39
      output_tokens: 1104
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 39
    output_tokens: 1104
    cost_usd: 0.0
    recorded_at: '2026-07-18T02:06:53.693341+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-41 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-41.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-41.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-41.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-41.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-41 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-41.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-41.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-41.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/done/TRICKLE-41.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 29d18ddeb46809e8
- dedup_fingerprint: 29d18ddeb46809e8
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/433
- Requestor: @NVShawn
- Reference: lesserevil/oompah#433

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-18 02:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-18 02:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-18 02:05
---
Understanding: This issue is about a duplicate task ID error in backend:oompah_md_tracker. When TRICKLE-41.md exists in both .oompah/tasks/done/ and .oompah/tasks/merged/, the tracker logs an error and files it via error_watcher. The desired fix is either to prevent such duplicate detection from being treated as an error (or to handle it gracefully). My role is Duplicate Investigator — I'll search for any previously-handled issues covering the same duplicate-task-ID problem before any implementation begins.
---
author: oompah
created: 2026-07-18 02:06
---
Discovery: OOMPAH-228 is a confirmed duplicate of OOMPAH-220. Evidence:\n\n1. OOMPAH-220 (trickle-30, same error pattern, now Merged) was the canonical report for this entire bug class.\n2. The OOMPAH-220 duplicate_detector comment at 2026-07-18 01:14 explicitly listed OOMPAH-228 (trickle-41) as a sibling duplicate.\n3. The root cause — logger.error() at oompah/oompah_md_tracker.py:871 in _read_records() — was fixed by a Maintenance Engineer: downgraded to logger.warning() in commit 625014c3, merged via PR #438.\n4. Test test_duplicate_task_id_logs_warning_not_error was added to prevent regression.\n5. make test passed: 9054 passed, 36 skipped, 0 failures.\n\nThis issue is a duplicate-of:OOMPAH-220. Archiving.
---
author: oompah
created: 2026-07-18 02:06
---
duplicate-of:OOMPAH-220
---
author: oompah
created: 2026-07-18 02:06
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 22
- Tokens: 39 in / 1.1K out [1.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 12s
- Log: OOMPAH-228__20260718T020448Z.jsonl
---
<!-- COMMENTS:END -->
