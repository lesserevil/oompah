---
id: OOMPAH-503
type: bug
status: Backlog
priority: 1
title: Limit automatic duplicate detection to nonterminal tasks
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:05:59.013552Z'
updated_at: '2026-07-28T17:44:09.301343Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 97f1c0a8-978f-4528-98ed-ac08e35f86c1
oompah.work_branch: epic-OOMPAH-502
---
## Summary

Problem: _apply_duplicate_detection currently fetches both active and terminal task states. Similar Done, Merged, or Archived tasks route new work through a Duplicate Investigator, adding minutes and large prompt replay even though the accepted workflow now defines automatic duplicate detection as active-work collision prevention only.

Implementation: in oompah/orchestrator.py and oompah/focus.py, build each project comparison pool exclusively from canonical nonterminal states. Never fetch or compare configured terminal states, including aliases/case variants. Preserve self-exclusion, focus-complete suppression, active duplicate-candidate handling, per-project tracker routing, bounded candidate scanning, and explicit/manual duplicate_detector focus behavior. Update comments/docs that describe open+closed comparison.

Tests: update tests/test_orchestrator_duplicate_detection.py and tests/test_focus.py. Assert Done, Merged, Archived, and a configured custom terminal alias are absent from the fetched pool and cannot add needs:duplicate_detector; assert Open/In Progress matches still block as duplicate candidates; cover native, GitHub, and GitLab tracker-neutral state lists; run focused tests and make test at the final branch gate.

Acceptance criteria: terminal task history can never trigger automatic duplicate screening or a duplicate-detector agent; active duplicate collisions remain blocked; metrics remain accurate; no tracker performs a terminal-state duplicate query.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:06
---
Claimed for manual implementation by the current Codex session. Held in Backlog while the shared epic branch is built so Oompah does not dispatch another agent; status will move to In Progress and Done as this session completes the slice.
---
author: oompah
created: 2026-07-28 15:07
---
Understanding: automatic duplicate detection will become active-work collision detection only. I will fetch only configured active states, defensively filter any terminal records returned by a tracker, remove the closed-match auto-handoff path, and retain explicit/manual duplicate_detector focus support.
---
author: oompah
created: 2026-07-28 15:10
---
Implemented on epic-OOMPAH-502 in commit 91d6c4344. Automatic duplicate detection now requests only configured active states and defensively removes terminal records returned by over-broad trackers; the former terminal-match duplicate-detector handoff was removed. Focused regression suite: 160 passed.
---
author: oompah
created: 2026-07-28 15:10
---
Terminal tasks are excluded from automatic duplicate detection at query and filtering boundaries; regression tests pass.
---
author: oompah
created: 2026-07-28 17:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 17:43
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
