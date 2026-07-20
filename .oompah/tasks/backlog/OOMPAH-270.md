---
id: OOMPAH-270
type: task
status: Backlog
priority: null
title: Add retry-with-backoff for transient git lock errors in _git() / _commit_and_push()
parent: OOMPAH-268
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-20T17:13:50.286632Z'
updated_at: '2026-07-20T17:13:50.286632Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

## Summary

Implement retry-with-exponential-backoff in OompahMarkdownTracker._git() for transient git lock contention errors. When a concurrent git process holds .git/index.lock or the ref lock, the current code raises TrackerError immediately, causing the 'Add comment API error' to be logged to error_watcher and auto-filed as a bug. The fix should transparently retry and succeed without surfacing the error.

## Context

- **File**: oompah/oompah_md_tracker.py
- **Method**: _git() (at bottom of file) and _commit_and_push()
- **Error triggers**: 'git add .oompah/tasks' and 'git commit' can fail with:
  - 'fatal: Unable to create ... .git/index.lock: File exists'
  - 'fatal: cannot lock ref HEAD'
- **Root cause**: threading.RLock only serializes within-process threads; concurrent external git processes (e.g. agent worktrees) can still hold the git index lock.
- **Related**: OOMPAH-267 has the same root cause ('cannot lock ref HEAD') and will be resolved by the same fix.

## Implementation Scope

In oompah/oompah_md_tracker.py:

1. Add a helper function or modify _git() to detect transient lock error patterns in stderr:
   - 'index.lock': File exists'
   - 'cannot lock ref'
   - 'Unable to create' + '.lock'

2. When a transient lock error is detected, retry with exponential backoff:
   - Up to 3 retries (total 4 attempts)
   - Delays: 0.5s, 1.0s, 2.0s (or similar, totaling ~3.5s max wait)
   - Log a warning on each retry attempt

3. After max retries, raise the original TrackerError (don't swallow the error permanently — if a lock persists for >4s something else is wrong).

4. Non-lock git errors must NOT be retried (fail fast for auth errors, etc.).

## Test Requirements

In tests/test_oompah_md_tracker.py:

- Test: git add fails with 'index.lock' error once, then succeeds on retry → verify operation completes
- Test: git commit fails with 'cannot lock ref HEAD' once, then succeeds on retry → verify operation completes
- Test: lock error persists beyond all retries → verify TrackerError is raised
- Test: non-lock git error (e.g. 'authentication failed') is NOT retried → verify immediate failure
- Use existing test patterns: mock subprocess.run via unittest.mock.patch, use _make_completed_process() helper

## Acceptance Criteria

- [ ] _git() retries on stderr patterns matching transient git lock errors
- [ ] Retry uses exponential backoff (3 retries max)
- [ ] Non-lock errors are not retried
- [ ] After max retries, TrackerError is raised (not silently swallowed)
- [ ] All 4 regression tests pass
- [ ] make test passes with no regressions
- [ ] OOMPAH-267 is also resolved (verify by inspection — same code path)

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

