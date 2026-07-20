---
id: OOMPAH-163
type: bug
status: Archived
priority: 1
title: Allow generated epic target branches through dispatch
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-10T17:20:29.690205Z'
updated_at: '2026-07-17T18:11:12.475976Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5b828242-41fa-40cf-a89f-f98f75667e8a
---
## Summary

Stacked/shared child tasks can carry oompah-generated target branches like epic-COROOT-5. The generic target_branch validator currently rejects those branches when a project only tracks main, so Needs CI Fix and Needs Rebase child tasks are considered but never receive agents. Oompah-owned epic branches should bypass the configured branch allowlist when the target matches epic-<parent_id>.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-10 17:21
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-10 17:21
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-10 17:26
---
Understanding: The dispatch-wide target_branch allowlist blocks stacked/shared repair tasks whose target is the generated parent epic branch. I will reproduce the rejection, allow only the exact branch generated from parent_id, retain validation for all other targets, and cover Needs CI Fix/Needs Rebase with regression tests.
---
author: oompah
created: 2026-07-10 17:26
---
Discovery: Reproduced in tests/test_release_pick_validation.py: _should_dispatch sends every non-empty target_branch through validate_release_pick_target, which rejects epic-COROOT-5 when project.branches is only main. There was no parent-epic exception.
---
author: oompah
created: 2026-07-10 17:26
---
Implementation: _should_dispatch now bypasses the configured branch allowlist only when target_branch exactly equals ProjectStore.epic_branch_name(issue.parent_id). Added regression coverage for Needs CI Fix and Needs Rebase plus a negative mismatched epic-* target.
---
author: oompah
created: 2026-07-10 17:27
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/default]
- Turns: 0, Tool calls: 24
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 52s
- Log: OOMPAH-163__20260710T172139Z.jsonl
---
author: oompah
created: 2026-07-10 17:29
---
Fixed dispatch target validation so oompah-generated epic branches (target_branch == epic-<parent_id>) bypass the project branches allowlist while mismatched or operator-specified branches remain validated. Added release-pick validation and _should_dispatch regressions for Needs CI Fix/Needs Rebase child repairs. Verification: make test passed with 7466 passed, 5 skipped. Deployed by restarting the server to pid 3885560; coroot repairs that were previously blocked are now dispatching (COROOT-19/COROOT-20 Needs Rebase running, COROOT-21 Needs CI Fix dispatched).
---
<!-- COMMENTS:END -->
