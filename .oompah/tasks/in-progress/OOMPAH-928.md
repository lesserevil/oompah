---
id: OOMPAH-928
type: bug
status: In Progress
priority: 1
title: Bound epic restart cleanup seeding and aggregate historical uncertainty
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T23:09:00.912201Z'
updated_at: '2026-08-08T23:35:19.730398Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-763

All-enforce restart on ce8b839811c2f0ff297179278aa3aa6171c5705b scanned 126 epics and emitted 86 one-per-task WARNING records for historical Merged/Archived epics whose already-pruned source generation is legitimately unavailable. The restart seed in oompah/epic_workflow_adapter.py schedules CLEANUP for every terminal epic, performs serialized tracker/forge/Git fact work, increments its scheduled count even when _schedule defers without enqueuing, and treats expected historical cleanup uncertainty as individually actionable. Refactor restart seeding to keep current retained cleanup authority fail-closed while avoiding unnecessary historical terminal cleanup work where absence is proven, make scheduling counts reflect actual enqueues, demote/suppress non-actionable per-epic noise, and emit at most one bounded aggregate startup summary. Add regression tests covering mixed current/historical terminal epics, exact-generation absence, actual retained cleanup failures, count accuracy, bounded log cardinality/severity, and idempotent restart behavior. Run focused epic workflow adapter tests and the complete make test gate. Acceptance: restart does not emit one warning per safely pruned historical epic; actionable retained cleanup uncertainty remains visible; reported counts equal durable jobs actually scheduled; startup work is bounded and does not create duplicate cleanup jobs.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 23:35
---
Implementation complete in the shared candidate worktree: restart cleanup seeding now counts only newly created durable jobs, is stable across runtime owner/process restarts, avoids collector/Git work for terminal epics without tracker exact heads, classifies retained durable cleanup authority, and emits exactly one bounded aggregate summary per seed pass. Focused epic workflow and adapter suite: 81 passed. Awaiting integration with OOMPAH-927 and the exact full branch gate.
---
<!-- COMMENTS:END -->
