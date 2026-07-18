---
id: OOMPAH-222
type: bug
status: Archived
priority: 2
title: '[backend:oompah_md_tracker] Duplicate native oompah task ID trickle-32 at
  /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-32.md and
  /home/shedwards/.oompah/repos/trickle/.oo...'
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-18T01:07:12.334359Z'
updated_at: '2026-07-18T01:32:18.374300Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#427
  owner: lesserevil
  repo: oompah
  number: '427'
  url: https://github.com/lesserevil/oompah/issues/427
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-18T01:15:45.325448+00:00'
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
  last_validated_at: '2026-07-18T01:08:33.171527+00:00'
oompah.agent_run_id: 3214432e-95bd-4b77-9811-aa15320bd3d0
oompah.task_costs:
  total_input_tokens: 56
  total_output_tokens: 1896
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 56
      output_tokens: 1896
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 56
    output_tokens: 1896
    cost_usd: 0.0
    recorded_at: '2026-07-18T01:15:42.592322+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:oompah_md_tracker`:

> Duplicate native oompah task ID trickle-32 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-32.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-32.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-32.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-32.md. Repair the stale record before editing this task.

### Desired Behavior

The operation in `backend:oompah_md_tracker` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:oompah_md_tracker` active.
2. Let oompah execute the operation that involves `backend:oompah_md_tracker` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:oompah_md_tracker` and is recorded by oompah's `error_watcher`:

> Duplicate native oompah task ID trickle-32 at /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-32.md and /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-32.md; using /home/shedwards/.oompah/repos/trickle/.oompah/tasks/merged/TRICKLE-32.md and ignoring /home/shedwards/.oompah/repos/trickle/.oompah/tasks/in-progress/TRICKLE-32.md. Repair the stale record before editing this task.

### Acceptance Criteria

- The error from `backend:oompah_md_tracker` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 41cbe445d6c2baf1
- dedup_fingerprint: 41cbe445d6c2baf1
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/427
- Requestor: @NVShawn
- Reference: lesserevil/oompah#427

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
Understanding: Investigating whether OOMPAH-222 (duplicate native oompah task ID error in backend:oompah_md_tracker) is a duplicate of an existing issue. The error occurs when a task file exists in two state directories simultaneously (in-progress/ and merged/), causing the tracker to emit a duplicate-ID warning captured by error_watcher. Will search existing tasks for prior reports of this same error pattern.
---
author: oompah
created: 2026-07-18 01:14
---
Discovery: Duplicate screening complete — OOMPAH-222 is NOT a duplicate.

**Closest related task reviewed:** OOMPAH-212 (Merged, 2026-07-16) — 'Prevent duplicate native task records from appearing on the board'
- OOMPAH-212 added the winner/loser deduplication logic in oompah/oompah_md_tracker.py (around line 862-879), selecting the most-recently-updated file when a task appears in two state directories simultaneously.
- OOMPAH-212 is NOT the same issue: it fixed the board display (prevents duplicates from appearing as separate entries). It did NOT prevent the error from being reported to error_watcher.

**Root cause of OOMPAH-222:** The deduplication code (oompah/oompah_md_tracker.py:872) uses logger.error() when a duplicate ID is detected. Error_watcher picks up logger.error() messages and auto-files them as bugs. The fix in OOMPAH-212 made the tracker handle duplicates gracefully but still emits an error-level log, triggering error_watcher.

**Scale of the problem:** 13 instances total filed on 2026-07-18 — OOMPAH-220 (TRICKLE-30), OOMPAH-221 (TRICKLE-31), OOMPAH-222 (TRICKLE-32), OOMPAH-223 through OOMPAH-232 (TRICKLE-36 through TRICKLE-45) — all describe the identical root cause.

**Evidence files:** oompah/oompah_md_tracker.py line 872 (logger.error call in the duplicate-resolution block)
---
author: oompah
created: 2026-07-18 01:15
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-222 is a distinct issue from OOMPAH-212 (Merged).

**Relevant files and evidence:**
- oompah/oompah_md_tracker.py:872 — `logger.error()` call inside the duplicate-ID resolution block. This is what error_watcher captures to auto-file these bugs.
- OOMPAH-212 (Merged) added winner/loser deduplication logic but uses logger.error(), so error_watcher still fires.
- 13 concurrent sibling tasks: OOMPAH-220, OOMPAH-221, OOMPAH-223 through OOMPAH-232 — all the same root cause, different TRICKLE task IDs.

**Remaining work:**
1. Downgrade `logger.error()` to `logger.warning()` at oompah/oompah_md_tracker.py:872 so error_watcher is not triggered (the situation is handled gracefully — no new error should be filed). This single change fixes all 13 instances.
2. Optionally: repair the stale in-progress/done/in-review files in the trickle managed repo to prevent recurrence.
3. Add a regression test confirming the duplicate-ID path emits a warning (not error) and does NOT trigger error_watcher behavior.

**Risks:** Ensure error_watcher is selective enough that downgrading this specific log level doesn't mask real errors.

**Recommended next focus:** bug (fix logger.error → logger.warning in duplicate-ID block; add regression test; optionally repair stale trickle files)
---
author: oompah
created: 2026-07-18 01:15
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 35
- Tokens: 56 in / 1.9K out [2.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 20s
- Log: OOMPAH-222__20260718T011130Z.jsonl
---
author: oompah
created: 2026-07-18 01:16
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-18 01:16
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-18 01:19
---
Understanding: As Epic Planner, I'm decomposing the work identified by the duplicate_detector agent into actionable child tasks.

**Root cause confirmed:** `oompah/oompah_md_tracker.py:871` uses `logger.error()` in the duplicate-ID deduplication block (`_read_records()`). The `error_watcher` logging handler (line 84 in `oompah/error_watcher.py`) is set to `logging.ERROR` level, so it captures this message and auto-files a bug task.

**The situation is already handled gracefully** — the winner/loser selection is correct, no data is lost. The only problem is the log level. Downgrading to `logger.warning()` fixes all 13 sibling tasks at once.

**Decomposition plan:**
1. Child task: Fix logger.error → logger.warning + add regression test (single session, bug fix agent)
2. No additional child tasks needed — the stale trickle repo files will be cleaned up through normal git operations and are not a code change in this repo
---
<!-- COMMENTS:END -->
