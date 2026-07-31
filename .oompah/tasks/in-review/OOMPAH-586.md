---
id: OOMPAH-586
type: epic
status: In Review
priority: 0
title: Restore least-privilege task and lifecycle access
parent: OOMPAH-584
children:
- OOMPAH-593
- OOMPAH-594
- OOMPAH-595
blocked_by: []
start_blocked_by: []
labels:
- merge-conflict
- epic:rebasing
assignee: null
created_at: '2026-07-30T14:13:33.901470Z'
updated_at: '2026-07-31T00:27:22.419306Z'
work_branch: epic-OOMPAH-586
target_branch: epic-OOMPAH-584
review_url: https://github.com/lesserevil/oompah/pull/597
review_number: '597'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/597
oompah.review_number: '597'
oompah.work_branch: epic-OOMPAH-586
oompah.target_branch: epic-OOMPAH-584
oompah.agent_run_id: f7d66fe8-6544-4878-bfab-c6c2704820d7
---
## Summary

Goal

Restore reliable operator and service-launched worker access to the oompah task API without distributing server-wide credentials to agents. Integrate the existing OOMPAH-575 scoped-auth work, cover credential reload/drift, and make lifecycle health failures actionable.

Relevant context

Plain task CLI calls from repair workers returned HTTP 401. The running server also retained stale Basic-auth state until recycled even though the current on-disk htpasswd and client password matched. OOMPAH-575 already implements scoped Codex handoff regression coverage and must be reused rather than duplicated.

Acceptance criteria

Assigned workers can view/comment/submit only their task; unrelated or expired capabilities fail closed; operator status/restart/task commands survive supported credential rotation or report a precise actionable fault; secrets are never exposed to workers/logs; focused and complete Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-31 00:25
---
Branch quality gate passed for `ca49d0c25b30d149cb59f0af0bac57276c1f8120` using `make test` in 260.9s. Review creation may proceed.
---
author: oompah
created: 2026-07-31 00:26
---
YOLO: Merge conflict detected on MR #597. Rebase `epic-OOMPAH-586` onto epic-OOMPAH-584 and resolve conflicts.
---
author: oompah
created: 2026-07-31 00:26
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-31 00:26
---
Focus: Merge Conflict Resolver
---
<!-- COMMENTS:END -->
