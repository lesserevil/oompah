---
id: OOMPAH-1266
type: bug
status: Open
priority: 1
title: Fence late task submission from regressing landed integration authority
parent: OOMPAH-1231
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-14T04:54:34.556175Z'
updated_at: '2026-08-14T05:13:15.343511Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: o1263-post-merge-submit-provenance-regression
  request_fingerprint: 9a9d8d03687f81678f5061a4c7f6ca12b789b64399e6fd9b92b89ef14dc3e4b5
oompah.lifecycle_revision: 1
---
## Summary

A pull-request closed+merged webhook can stage terminal evidence before a delayed `oompah task submit` arrives. Reproduced on OOMPAH-1263: PR 880 merged into epic-OOMPAH-1231 and staged Done, then the later submit replaced the landed/integrated projection with a `ready` IntegrationRecord at reviewed head 987c46c. The active audit retained the earlier fingerprint, so every owner override returned terminal fingerprint mismatch until a fresh normal Done request superseded the stale audit. Implement an atomic authority fence across submission, integration queue, native tracker integration metadata, and merged-review reconciliation so a late or retried submit cannot change an integrated generation back to ready or cause duplicate delivery. If the review is already merged, either preserve/repair the exact integrated record using forge-confirmed landed SHA or reject the stale submit with an actionable idempotent result. Add regression tests for webhook-before-submit, submit-before-webhook, lost-response retry, restart between the two events, mismatched head/base, and concurrent replacement generation. Verify terminal fingerprint remains stable and the task cannot be reintegrated. Relevant areas: task submit API/service, integration_queue CAS, native integration metadata, PR webhook/reconciliation, terminal fingerprint tests. Acceptance: exact landed authority is monotonic, same-generation late submits are idempotent, mismatched submissions fail closed, and terminal override/audit no longer deadlocks after this ordering.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 04:56
---
Claimed directly on branch OOMPAH-1266 in /home/shedwards/src/oompah-1266 from origin/epic-OOMPAH-1231. Reproducing the webhook-before-submit metadata regression and implementing the smallest monotonic integration-authority fence with same-generation retry idempotency and replacement fail-closed coverage. I will not push, submit, or change terminal status.
---
author: oompah
created: 2026-08-14 05:13
---
Implementation complete on local branch OOMPAH-1266 at 91a0d0842784bd42aba8324c86a4a6b026b4dbba. The submit path now preserves exact integrated tracker authority, rejects changed head/base generations, repairs the queue-first restart gap, and avoids queue rearm, lifecycle regression, duplicate coordination, or validation reflow after landing. Integrated queue rows are immutable under exact retry/replacement races, and landed retry retirement is generation-fenced so a successor worker survives. Regression coverage includes webhook-before-submit, submit-before-webhook, lost-response retry, restart gap, mismatched head/base, concurrent replacement, terminal fingerprint stability, and durable authority retirement. Verification: 928 tests passed across submission, handoff, queue, webhook, integration/review workflow, implementation fencing, and terminal fingerprint/transition suites. Focused Ruff checks pass for the directly changed queue/adapter and their new tests; the broad server/test invocation reports pre-existing lint debt outside this change. Per coordination instructions, this commit is local only: not pushed, submitted, or status-transitioned.
---
<!-- COMMENTS:END -->
