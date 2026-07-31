---
id: OOMPAH-642
type: task
status: Open
priority: null
title: Fence standalone delivery gate outcomes after terminal authority changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T06:09:07.190386Z'
updated_at: '2026-07-31T06:09:09.996500Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Race reproduced during post-restart recovery: OOMPAH-575 had a standalone branch gate already running; the project owner applied a verified Merged override because the branch equaled main and PR #604 had zero diff; after the override revoked delivery authority, the terminated gate still committed Needs CI Fix and emitted a stranded-delivery alert. Implementation scope: make standalone Ready delivery and review-gate completion use a compare-and-swap authority token or task evidence revision before every tracker mutation, alert mutation, queue update, and retry scheduling. A gate whose task became Done, Merged, Archived, changed branch/head, or otherwise lost delivery authority must record a superseded/cancelled diagnostic only and must not regress status. Reuse the integration executor commit_allowed/fencing model where possible and ensure terminal owner overrides synchronously revoke pending standalone delivery ownership. Relevant files: standalone Ready reconciliation, branch quality gate orchestration, review creation, terminal transition callbacks, and delivery-plane alert cleanup. Tests: deterministic barrier race with gate in flight then Merged override; gate failure and success after authority revocation; changed head; process restart with stale gate record; repeated ticks; alert clearing; no duplicate PR or retry. Acceptance: no stale gate outcome can overwrite a newer terminal or evidence revision, current OOMPAH-575 reproduction stays Merged, focused race/delivery tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

