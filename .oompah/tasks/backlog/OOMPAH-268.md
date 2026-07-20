---
id: OOMPAH-268
type: bug
status: Backlog
priority: 2
title: '[backend:server] Add comment API error: git add .oompah/tasks failed: fatal:
  Unable to create ''/home/shedwards/.oompah/repos/oompah/.git/index.lock'': File
  exists.


  Another git process seems to be r...'
parent: null
children:
- OOMPAH-270
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-20T16:52:04.570031Z'
updated_at: '2026-07-20T17:14:14.379485Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#454
  owner: lesserevil
  repo: oompah
  number: '454'
  url: https://github.com/lesserevil/oompah/issues/454
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-20T16:58:34.934440+00:00'
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
  last_validated_at: '2026-07-20T16:52:15.589069+00:00'
oompah.agent_run_id: 93d34c55-0918-49b0-83c2-93cc51c494a9
oompah.task_costs:
  total_input_tokens: 96294
  total_output_tokens: 16001
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 96294
      output_tokens: 16001
      cost_usd: 0.0
  runs:
  - profile: deep
    model: unknown
    input_tokens: 48
    output_tokens: 15306
    cost_usd: 0.0
    recorded_at: '2026-07-20T17:07:21.374805+00:00'
  - profile: deep
    model: unknown
    input_tokens: 96246
    output_tokens: 695
    cost_usd: 0.0
    recorded_at: '2026-07-20T17:08:16.371199+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:server`:

> Add comment API error: git add .oompah/tasks failed: fatal: Unable to create '/home/shedwards/.oompah/repos/oompah/.git/index.lock': File exists.

Another git process seems to be running in this repository, e.g.
an editor opened by 'git commit'. Please make sure all processes
are terminated then try again. If it still fails, a git process
may have crashed in this repository earlier:
remove the file manually to continue.

### Desired Behavior

The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:server` active.
2. Let oompah execute the operation that involves `backend:server` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Add comment API error: git add .oompah/tasks failed: fatal: Unable to create '/home/shedwards/.oompah/repos/oompah/.git/index.lock': File exists.

Another git process seems to be running in this repository, e.g.
an editor opened by 'git commit'. Please make sure all processes
are terminated then try again. If it still fails, a git process
may have crashed in this repository earlier:
remove the file manually to continue.

### Acceptance Criteria

- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: bed1bd7effec3bb8
- dedup_fingerprint: bed1bd7effec3bb8
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/454
- Requestor: @NVShawn
- Reference: lesserevil/oompah#454

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 16:56
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 16:56
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 16:56
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 43s
- Log: OOMPAH-268__20260720T165623Z.jsonl
---
author: oompah
created: 2026-07-20 16:57
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-20 16:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 17:05
---
Understanding: Investigating OOMPAH-268 as Duplicate Investigator. The issue is an auto-filed error_watcher report for a git index.lock contention failure in oompah_md_tracker.add_comment() → _commit_and_push() → _git(['add', TASKS_DIR]). The fingerprint (bed1bd7effec3bb8) is unique to this specific error message.

Plan: (1) search .oompah/tasks/ for prior tasks with same root cause; (2) check archived/done tasks for prior resolutions; (3) compare with OOMPAH-267 (a sibling error with same code path but different git command).
---
author: oompah
created: 2026-07-20 17:06
---
Focus handoff: duplicate_detector

**Outcome:** No confirmed duplicate found. OOMPAH-268 is NOT a duplicate of any resolved/done/archived task.

**Evidence reviewed:**
- Searched .oompah/tasks/ (all statuses) for: index.lock, git lock, git add failed, concurrent git, Add comment API error, bed1bd7effec3bb8 fingerprint
- Reviewed archived tasks with 'git add', 'lock', 'concurrent': OOMPAH-176, OOMPAH-222, OOMPAH-227, OOMPAH-229, OOMPAH-29 — none match this error
- OOMPAH-189 (Archived): Similar 'Add comment API error' but about git merge divergence, not index.lock — different root cause, resolved as stale
- OOMPAH-235 (Done): 'Recover native tracker writes after concurrent default-branch advancement' — fixed push-race rebase logic, but does NOT address index.lock from concurrent git processes
- OOMPAH-203 (Done): Auto-update restart prevention — unrelated
- OOMPAH-156 (Archived): error_watcher dedup fingerprint logic — implemented, not directly relevant

**Closest related (but NOT duplicates):**
- OOMPAH-267 (Open): Also 'Add comment API error' in same code path (oompah_md_tracker._commit_and_push), but fails at git commit with 'cannot lock ref HEAD' rather than git add with 'index.lock'. Same root cause (concurrent git ops), different failure mode, different fingerprint, filed ~1 min earlier. Will likely be fixed by the same implementation.
- OOMPAH-253 epic / OOMPAH-257 (Open): Architecture redesign for coalesced state-branch checkpoints — addresses the long-term systemic fix but not an immediate duplicate.

**Root cause:** oompah_md_tracker._commit_and_push() runs git add .oompah/tasks under threading.RLock(), but RLock only serializes within-process threads. Concurrent git processes (agent worktrees or parallel server tasks) can also hold the index.lock, causing this failure. The fix is retry logic with backoff for index.lock contention in _git() / _commit_and_push(). See oompah/oompah_md_tracker.py lines 1041-1060.

**Remaining work:**
- Add retry-with-backoff handling when git add / git commit fails with index.lock or similar transient lock errors
- The fix likely resolves OOMPAH-267 as well (same code path, similar retry needed)
- Tests: simulate concurrent index.lock scenario, verify retry succeeds

**Recommended next focus:** backend (bug fix in oompah/oompah_md_tracker.py)
---
author: oompah
created: 2026-07-20 17:07
---
Agent completed successfully in 596s (15354 tokens)
---
author: oompah
created: 2026-07-20 17:07
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 99, Tool calls: 69
- Tokens: 48 in / 15.3K out [15.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 56s
- Log: OOMPAH-268__20260720T165747Z.jsonl
---
author: oompah
created: 2026-07-20 17:07
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-20 17:07
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-20 17:07
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-20 17:08
---
Agent completed successfully in 31s (96941 tokens)
---
author: oompah
created: 2026-07-20 17:08
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 96.2K in / 695 out [96.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 31s
- Log: OOMPAH-268__20260720T170756Z.jsonl
---
author: oompah
created: 2026-07-20 17:08
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-268`. No stronger profile is configured; retrying with 'deep' in 10s (1/3).
---
author: oompah
created: 2026-07-20 17:08
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-20 17:08
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-20 17:13
---
Understanding (Epic Planner): This bug involves git index.lock contention in OompahMarkdownTracker._git() / _commit_and_push(). When a concurrent git process holds .git/index.lock, git add .oompah/tasks fails immediately with no retry. The same code path also fails with 'cannot lock ref HEAD' (see OOMPAH-267).

Root cause: _git() uses subprocess.run with check=True but no retry logic for transient lock errors. The threading.RLock serializes within-process threads, but cannot prevent concurrent external git processes (e.g. agent worktrees) from holding index.lock.

Decomposition: This is a focused bug fix scoped to oompah/oompah_md_tracker.py and tests/test_oompah_md_tracker.py. I will create one child task covering implementation + tests together, since they are tightly coupled per project policy.
---
author: oompah
created: 2026-07-20 17:14
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 13
- Tokens: 30 in / 443 out [473 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 24s
- Log: OOMPAH-268__20260720T170858Z.jsonl
---
<!-- COMMENTS:END -->
