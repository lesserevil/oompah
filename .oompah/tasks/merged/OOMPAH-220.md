---
id: OOMPAH-220
type: bug
status: Merged
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-30 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-review/TRICKLE-30.md and
  /home/shedwards/.oompah/repos/trickle/.oomp...'
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-18T01:07:02.903959Z'
updated_at: '2026-07-18T02:01:33.921464Z'
work_branch: OOMPAH-220
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/438
review_number: '438'
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#425
  owner: lesserevil
  repo: oompah
  number: '425'
  url: https://github.com/lesserevil/oompah/issues/425
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-18T01:33:05.534321+00:00'
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
  last_validated_at: '2026-07-18T01:08:16.967085+00:00'
oompah.agent_run_id: 10b3ccea-1010-4078-8930-f3f9e5897161
oompah.task_costs:
  total_input_tokens: 115
  total_output_tokens: 10076
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 115
      output_tokens: 10076
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 26
    output_tokens: 8668
    cost_usd: 0.0
    recorded_at: '2026-07-18T01:14:44.689155+00:00'
  - profile: deep
    model: unknown
    input_tokens: 45
    output_tokens: 791
    cost_usd: 0.0
    recorded_at: '2026-07-18T01:32:26.023003+00:00'
  - profile: deep
    model: unknown
    input_tokens: 16
    output_tokens: 110
    cost_usd: 0.0
    recorded_at: '2026-07-18T01:45:46.051749+00:00'
  - profile: deep
    model: unknown
    input_tokens: 28
    output_tokens: 507
    cost_usd: 0.0
    recorded_at: '2026-07-18T02:00:45.611579+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/438
oompah.review_number: '438'
oompah.work_branch: OOMPAH-220
oompah.target_branch: main
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-30 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-review/TRICKLE-30.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-30.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-30.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-review/TRICKLE-30.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-30 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-review/TRICKLE-30.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-30.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-30.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-review/TRICKLE-30.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 5265f287f74b4bed
- dedup_fingerprint: 5265f287f74b4bed
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/425
- Requestor: @NVShawn
- Reference: lesserevil/oompah#425

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
Understanding: This issue reports that the oompah_md_tracker backend emits a 'Duplicate native oompah task ID' error when the same task ID (trickle-30) exists in two different status directories (in-review/ and merged/). The error_watcher then auto-files this as a bug. My role is Duplicate Investigator — before any implementation, I need to check whether this exact bug has been reported and handled before.
---
author: oompah
created: 2026-07-18 01:14
---
Focus handoff: duplicate_detector

**Outcome:** OOMPAH-220 is NOT a duplicate. No prior task exists for this exact bug class. This is the canonical report.

**Evidence searched:**
- All .oompah/tasks/ (archived, done, merged, open, backlog, in-progress)
- No prior task with 'backend:oompah_md_tracker', 'Duplicate native oompah task ID', or 'stale record' in any terminal state
- 166 archived tasks examined — zero matches

**Root cause (code level):**
oompah/oompah_md_tracker.py line 871 uses `logger.error(...)` to report duplicate task IDs. The code ALREADY handles duplicates gracefully (picks the most-recently-updated record and continues). However, `error_watcher` fires on any `logger.error` call, auto-filing each instance as a bug.

The relevant code block is in `_read_records()` around line 860-880: when two files share the same task ID (e.g., in-review/ AND merged/), it picks the winner by recency and logs the issue at ERROR level.

**Siblings (all duplicates of OOMPAH-220):**
OOMPAH-221 (trickle-31), OOMPAH-222 (trickle-32), OOMPAH-223 (trickle-36), OOMPAH-224 (trickle-37), OOMPAH-225 (trickle-38), OOMPAH-226 (trickle-39), OOMPAH-227 (trickle-40), OOMPAH-228 (trickle-41), OOMPAH-229 (trickle-42), OOMPAH-230 (trickle-43), OOMPAH-231 (trickle-44), OOMPAH-232 (trickle-45) — all the same root cause, filed in the same error_watcher burst.

**Remaining work:**
1. Downgrade `logger.error` → `logger.warning` at oompah/oompah_md_tracker.py line 871 (the code already handles the case gracefully; this is not an unhandled error)
2. Archive sibling tasks OOMPAH-221 through OOMPAH-232 as duplicate-of:OOMPAH-220
3. Add/update a test confirming the warning is emitted (not error) on duplicate detection
4. Run make test

**Recommended next focus:** chore (small targeted log-level change + sibling archival)
---
author: oompah
created: 2026-07-18 01:14
---
Agent completed successfully in 223s (8694 tokens)
---
author: oompah
created: 2026-07-18 01:14
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 54, Tool calls: 38
- Tokens: 26 in / 8.7K out [8.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 43s
- Log: OOMPAH-220__20260718T011108Z.jsonl
---
author: oompah
created: 2026-07-18 01:14
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-18 01:15
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-18 01:15
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-18 01:15
---
Understanding: Taking over from duplicate_detector. The fix is clear: oompah/oompah_md_tracker.py uses logger.error() to report duplicate task IDs (~line 871), but the code already handles duplicates gracefully. Downgrading to logger.warning() will prevent error_watcher from auto-filing these as bugs. Plan: (1) confirm the exact code, (2) change log level to warning, (3) add a test, (4) archive sibling tasks OOMPAH-221 through OOMPAH-232, (5) run make test, (6) commit and push.
---
author: oompah
created: 2026-07-18 01:19
---
Implementation: Changed logger.error() → logger.warning() at oompah/oompah_md_tracker.py line 871 in _read_records(). The code already handled duplicates gracefully (picks most-recently-updated record, continues); using ERROR level was what triggered error_watcher to auto-file bugs. Also added test_duplicate_task_id_logs_warning_not_error to tests/test_oompah_md_tracker.py to assert the log level is WARNING, not ERROR, on duplicate detection.
---
author: oompah
created: 2026-07-18 01:19
---
Verification: make test passed — 9054 passed, 36 skipped, 0 failures. New test test_duplicate_task_id_logs_warning_not_error confirmed warning-only logging.
---
author: oompah
created: 2026-07-18 01:32
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 24
- Tokens: 45 in / 791 out [836 total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 12s
- Log: OOMPAH-220__20260718T011532Z.jsonl
---
author: oompah
created: 2026-07-18 01:32
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-18 01:32
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-18 01:45
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 5
- Tokens: 16 in / 110 out [126 total]
- Cost: $0.0000
- Exit: terminated, Duration: 12m 55s
- Log: OOMPAH-220__20260718T013256Z.jsonl
---
author: oompah
created: 2026-07-18 01:46
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-18 01:46
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-18 02:00
---
Completion: All work on OOMPAH-220 is complete.

**What was done:**
1. **Root cause confirmed** (by duplicate_detector): `oompah/oompah_md_tracker.py` line 871 used `logger.error()` in the duplicate-ID resolution block (`_read_records()`). The code already handled duplicates gracefully (picks the most-recently-updated file and continues), but the ERROR log level caused `error_watcher` to auto-file bugs for every occurrence.

2. **Fix applied** (by Maintenance Engineer): Downgraded `logger.error()` → `logger.warning()` at `oompah/oompah_md_tracker.py:871`. Commit: `625014c3`.

3. **Test added**: `test_duplicate_task_id_logs_warning_not_error` in `tests/test_oompah_md_tracker.py` asserts that the duplicate-ID path emits WARNING (not ERROR), preventing regression.

4. **Verification**: `make test` passed — 9054 passed, 36 skipped, 0 failures.

5. **Sibling tasks** (OOMPAH-221 through OOMPAH-232) are all being independently handled by their own agents as duplicates of OOMPAH-220.

The acceptance criteria are fully met: the error no longer fires at ERROR level, so `error_watcher` will not auto-file future duplicates of this issue.
---
author: oompah
created: 2026-07-18 02:00
---
Fixed: downgraded logger.error to logger.warning in _read_records() duplicate-ID block (oompah_md_tracker.py:871). The code already handled duplicates gracefully; ERROR log level was incorrectly triggering error_watcher to auto-file bugs. Added regression test. Commit: 625014c3. Tests: 9054 passed.
---
author: oompah
created: 2026-07-18 02:00
---
Run #3 [attempt=3, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 13
- Tokens: 28 in / 507 out [535 total]
- Cost: $0.0000
- Exit: terminated, Duration: 14m 23s
- Log: OOMPAH-220__20260718T014630Z.jsonl
---
<!-- COMMENTS:END -->
