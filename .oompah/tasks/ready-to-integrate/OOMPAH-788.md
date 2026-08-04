---
id: OOMPAH-788
type: feature
status: Ready to Integrate
priority: 1
title: Cut integration delivery over to shared decisions and durable jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:59:10.953215Z'
updated_at: '2026-08-04T18:22:59.296249Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-788
  head_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
  submitted_at: '2026-08-04T18:22:46.462761+00:00'
  updated_at: '2026-08-04T18:22:46.462761+00:00'
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-05ce75bec527
    project_id: proj-14849f1b
    task_id: OOMPAH-788
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 34c819f1efc49af72f9fd56df1fa0d756cb34d19a0435f02ef0352bb0ac2c59b
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct-owner implementation was fully tested and published at exact head
      08f6a8c5a on newly created parent branch epic-OOMPAH-768 while the operator
      intentionally paused scheduling. The running server is still revision a681ec2f
      and cannot execute the newly implemented durable integration path, so completion
      is recorded without asking the paused legacy integrator to mutate it.
    created_at: '2026-08-04T18:22:57.676219+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Migrate integration submission, eligibility, dependency satisfaction, claim, quality gate, ancestry repair, retry, terminal staging, and queue UI to WorkflowFacts/WorkDecision/workflow jobs/TaskTransitionService. Evaluate all topological heads rather than only the first Ready row; unify executor eligibility, metrics, waiting_on, and repair selection; preserve exact-head leases, fairness, audit staging, and historical queue migration. Required tests: mixed repairable/unrepairable rows, cross-epic reachability, hundreds of history rows, restart, retries, capacity, branch deletion, UI parity, and OOMPAH-562/749 scenarios. Acceptance: one integration decision powers execution and UI; every Ready task is claimed, concretely blocked, retry-scheduled, or escalated within SLO.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 18:22
---
Implemented the integration-domain cutover controller, durable handler, bounded executor-result classification, topological all-head evaluation, exact LandingFact verification, and decision-backed queue/UI projection. Fixed integrated records to schedule terminal staging only with exact target proof, otherwise informational landing refresh. Verification: 20 domain tests and 256 composed integration/workflow tests pass; Ruff, terminal scan, and secret scan pass. Exact pushed head: 08f6a8c5a.
---
author: oompah
created: 2026-08-04 18:22
---
Added shared-decision durable integration workflow at 08f6a8c5a.
---
<!-- COMMENTS:END -->
