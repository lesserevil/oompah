---
id: OOMPAH-787
type: task
status: In Progress
priority: 1
title: Complete shadow/enforce rollout, upgrade compatibility, and operator documentation
parent: OOMPAH-771
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-798
labels: []
assignee: null
created_at: '2026-08-04T13:59:09.296051Z'
updated_at: '2026-08-08T08:30:41.687833Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Implement per-domain .env/.env.example rollout controls, persisted-schema migrations, startup compatibility, safe rollback before final flag retirement, canary health gates, and final enforcement/default cleanup. Update user docs for why-not-progressing, action_required alerts, recovery, SLOs, upgrade/rollback, and architecture; update plans with internal design and delete contradictory descriptions. Verify live canary and production-like soak before removing shadow/legacy flags. Acceptance: upgrade from current persisted state is automatic and restart-safe; rollback boundaries are documented/tested; final configuration has no obsolete toggles; operators no longer need manual task-state workarounds for recoverable conditions.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 08:02
---
Direct implementation started in isolated branch direct/OOMPAH-787-on-systemic at exact systemic base 6cbbd6ef7bb7882257c4c9e9175bd5b3edc14183. Auditing shipped rollout/config/schema/docs first; will implement only remaining gaps and return a tested local commit for composition.
---
author: oompah
created: 2026-08-08 08:30
---
Direct implementation complete on isolated branch direct/OOMPAH-787-on-systemic at 106df6c547e5cc30be989ffef36978ebd279c29b (base 6cbbd6ef7bb7882257c4c9e9175bd5b3edc14183). Added four per-domain .env rollout modes with safe aggregate ownership, restart-persistent qualification/soak gates and state projection, interrupted schema-migration recovery, a bounded make workflow-rollout-check canary, final flag compatibility/retirement rules, and operator/internal rollout, recovery, why-not-progressing, alert, SLO, upgrade/rollback, and architecture docs. Exact final focused broker run: 85 passed; prior expanded run: 174 passed. Pycompile, focused Ruff, git diff check, terminal mutation scan, and secret scan passed. Worktree is clean and preserved for composition; no task status or remote was changed.
---
<!-- COMMENTS:END -->
