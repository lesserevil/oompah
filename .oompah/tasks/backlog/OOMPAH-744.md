---
id: OOMPAH-744
type: bug
status: Backlog
priority: 1
title: Atomically clear stale alert UI after authoritative resynchronization
parent: OOMPAH-740
children: []
blocked_by:
- OOMPAH-741
- OOMPAH-742
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T22:56:25.203763Z'
updated_at: '2026-08-03T22:57:14.311737Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Make alert and health presentation converge atomically whenever the dashboard receives an authoritative full state, including after a detected WebSocket sequence gap.

This task builds on OOMPAH-691 through OOMPAH-695. It does not redesign the sequencing protocol; it fixes the alert-derived DOM lifecycle that consumes the converged snapshot.

Scope:
- Treat every authoritative snapshot as a replacement for all alert, terminal-audit, quality-gate, authentication, and repository-health presentation state.
- Remove panels, list items, counts, badges, and stale CSS state for facts absent from the replacement snapshot.
- Prevent mixed-generation rendering where a new generic alert list is displayed beside old dedicated health panels.
- During Synchronizing state, keep the last known board usable, label its freshness compactly, and avoid presenting old warning facts as current after the replacement is available.
- Make incremental updates and full replacements share stable identity and ordering rules.
- Add bounded diagnostics for a presentation replacement failure without generating warning loops.

Relevant files: dashboard WebSocket and handleStateUpdate logic in oompah/templates/dashboard.html, full-sync response handling in oompah/server.py if needed, and OOMPAH-691 through OOMPAH-695 test harnesses.

Required tests:
- Transport failure to recovered zero removes every old failure rendering without refresh.
- Failed quality gate to running or idle replaces the old panel atomically.
- Dropped or reordered messages trigger full sync and leave exactly the authoritative alert set.
- A service epoch change cannot retain old alert DOM.
- Repeated identical snapshots do not duplicate alerts or announcements.

Acceptance criteria:
- After successful resynchronization, the browser alert center and status view exactly match the authoritative snapshot.
- No stale failure remains visible alongside recovered live state.
- Normal gap recovery remains non-alerting as specified by OOMPAH-695.
- Focused WebSocket, state reconciliation, and dashboard tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

