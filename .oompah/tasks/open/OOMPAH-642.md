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
updated_at: '2026-07-31T06:09:49.640929Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1c5eb493ad5a83b24b3efe1e89bfe4236f5090010e1e3df51ae69de95e27bc94
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 0357c8e3-de03-4d2a-aae9-c419c63ff7a5
  claim_owner: d12922aa-baf6-4258-aa45-02da3deea710
  claimed_at: '2026-07-31T06:09:44.134819+00:00'
  claim_expires_at: '2026-07-31T06:39:44.134819+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 6c2e9987-4937-4282-935b-ea927a4b6c48
---
## Summary

Race reproduced during post-restart recovery: OOMPAH-575 had a standalone branch gate already running; the project owner applied a verified Merged override because the branch equaled main and PR #604 had zero diff; after the override revoked delivery authority, the terminated gate still committed Needs CI Fix and emitted a stranded-delivery alert. Implementation scope: make standalone Ready delivery and review-gate completion use a compare-and-swap authority token or task evidence revision before every tracker mutation, alert mutation, queue update, and retry scheduling. A gate whose task became Done, Merged, Archived, changed branch/head, or otherwise lost delivery authority must record a superseded/cancelled diagnostic only and must not regress status. Reuse the integration executor commit_allowed/fencing model where possible and ensure terminal owner overrides synchronously revoke pending standalone delivery ownership. Relevant files: standalone Ready reconciliation, branch quality gate orchestration, review creation, terminal transition callbacks, and delivery-plane alert cleanup. Tests: deterministic barrier race with gate in flight then Merged override; gate failure and success after authority revocation; changed head; process restart with stale gate record; repeated ticks; alert clearing; no duplicate PR or retry. Acceptance: no stale gate outcome can overwrite a newer terminal or evidence revision, current OOMPAH-575 reproduction stays Merged, focused race/delivery tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 06:09
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-31 06:09
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
