---
id: OOMPAH-461
type: feature
status: Open
priority: 1
title: Add the canonical In Validation lifecycle status
parent: OOMPAH-457
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:05:03.234325Z'
updated_at: '2026-07-28T18:08:45.315770Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 1268a29c-34db-4073-b938-5a68cf9c7644
oompah.work_branch: epic-OOMPAH-457
---
## Summary

Implementation scope

Add IN_VALIDATION = "In Validation" to oompah/statuses.py and include it in canonical status parsing, ordering, and display lists. It must be nonterminal, non-working, and not ordinarily dispatchable. Update tracker/config status defaults and status-label conversion code only where required so native Markdown, GitHub Issues, and GitLab Issues can round-trip the value. Do not build the dashboard column or auditor scheduler in this task.

Tests

Add focused status tests for canonicalization, aliases, rank, terminal=false, working=false, and dispatchable=false. Add tracker serialization/label round-trip cases following existing status tests. Run the focused tests and make test.

Acceptance criteria

In Validation is accepted and returned consistently by every configured tracker, is not treated as Done/Merged/Archived, cannot enter ordinary worker dispatch, and does not change behavior of existing statuses.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:06
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:06
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 18:08
---
Duplicate screening complete: OOMPAH-461 is NOT a duplicate.

Evidence reviewed:
- Searched .oompah/tasks (archived, merged, open, backlog) for keywords: validation, status, lifecycle, canonical, IN_VALIDATION
- Searched docs/ and plans/ directories for IN_VALIDATION or validation status discussions
- Searched git log --all for commits mentioning 'In Validation', 'OOMPAH-461', or 'OOMPAH-457'
- Examined 25+ related tasks (OOMPAH-28, OOMPAH-252, etc.) covering status audits, lifecycle work, and existing canonicalization
- Reviewed statuses.py source code — no IN_VALIDATION constant currently exists
- Checked codebase for any prior 'In Validation' implementation attempts — none found

Closest candidates reviewed and ruled out:
- OOMPAH-28 (Archived): Audited existing 14 canonical statuses for 1.0 readiness; confirmed no gaps. Does not cover adding new statuses.
- OOMPAH-31 (Archived): Added Needs Answer / Needs Human intake statuses (separate prior feature); completed 2026-06-22. OOMPAH-461 targets a different status.
- All Release Delivery tasks (OOMPAH-200/236/252, etc.): Focus on dashboard UI/workflow, not status lifecycle.

Conclusion: OOMPAH-461 is a unique, original feature implementation task. No prior implementation or duplicate discovery found.
---
<!-- COMMENTS:END -->
