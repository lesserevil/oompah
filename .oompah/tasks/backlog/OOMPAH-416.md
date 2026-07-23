---
id: OOMPAH-416
type: task
status: Backlog
priority: null
title: Post REFRESH_REQUESTED after orphan resets to wake dispatch immediately
parent: OOMPAH-414
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T19:34:30.939292Z'
updated_at: '2026-07-23T19:34:30.939292Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

### Problem

_reset_orphaned_in_progress() (called in step 5c, fire-and-forget from the thread pool) resets orphaned In Progress tasks back to Open, but never notifies the dispatch loop. The dispatch loop only picks up the newly eligible tasks on the next full tick. During the July 23 incident, maintenance reset EXOCOMP-7 and EXOCOMP-41 *after* dispatch had already selected candidates, so they had to wait another full_sync_interval_ms (5 min) before dispatch. Operators patched this by manually POSTing /api/v1/refresh.

### Scope

In oompah/orchestrator.py, in the _reset_orphaned_in_progress() method:
- Track whether any issue was successfully reset (i.e., tracker.update_issue was called without exception and the issue was not preserved as Done).
- After the main reset loop, if any_reset is True, call: self._post_event(DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED))
- _post_event is already thread-safe (uses loop.call_soon_threadsafe when called from a background thread), so no additional locking is needed.
- Add a logger.info line to make the wake visible in logs: 'Orphan reset: %d issue(s) returned to Open — posting REFRESH_REQUESTED to wake dispatch immediately'

### Tests

Add a test in tests/test_dispatch_loop_heartbeat.py (or a new test file tests/test_orphan_reset_dispatch_wake.py):
- Test that _reset_orphaned_in_progress() posts exactly one REFRESH_REQUESTED event when at least one orphan is reset.
- Test that no REFRESH_REQUESTED event is posted when no orphans were reset (empty candidates, no in_progress issues).
- Mock tracker.update_issue and verify the event posting behavior.

Run make test before committing.

### Acceptance

After orphan resets, the dispatch loop wakes within milliseconds (via REFRESH_REQUESTED) rather than waiting for the next full tick (up to full_sync_interval_ms = 5 min). Newly-open Exocomp tasks are dispatched in the same tick or the immediately-following refresh tick, not on the next scheduled tick.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

