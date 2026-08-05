---
id: OOMPAH-768
type: epic
status: In Progress
priority: 1
title: Migrate every workflow domain to shared decisions and durable jobs
parent: OOMPAH-763
children:
- OOMPAH-781
- OOMPAH-782
- OOMPAH-788
- OOMPAH-791
- OOMPAH-793
- OOMPAH-804
- OOMPAH-812
- OOMPAH-813
- OOMPAH-819
blocked_by: []
start_blocked_by: &id001
- OOMPAH-766
labels:
- rebase-requested
assignee: null
created_at: '2026-08-04T13:55:59.817364Z'
updated_at: '2026-08-05T16:16:59.612282Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Cut over all task-progression domains to WorkflowFacts, WorkDecision, durable jobs, and TaskTransitionService in staged .env-controlled shadow/enforce modes. Domain scope: (1) integration queue eligibility, claiming, ancestry repair, UI waiting_on, retries, and fairness; (2) terminal-audit selection, launch, finalization, retry, and exhaustion; (3) In Review PR/CI/merge/missing-branch/capacity reconciliation; (4) implementation claims, direct-owner leases, worker exit, handoff, and retry; (5) epic/nested-epic rollup using first-class LandingFact(source,target,revision,proof) rather than status cycles. Remove duplicated predicates as each cutover completes. Required tests per domain include real native tracker and temporary Git/forge doubles plus restart and event-order races, with historical regressions preserved. Acceptance: each domain has exactly one eligibility/recovery decision, one durable owner, UI explanations match executor decisions, no parent-child proof cycles remain, and legacy domain writers/reconcilers are disabled after shadow parity.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 16:16
---
Direct-owner continuation: while OOMPAH-807's exact gate runs, the domain stack has been reconstructed in isolated scratch refs on candidate parent b1c089614. Duplicate patch-equivalent commits are omitted; OOMPAH-813 exact-project/replacement-run fences are composed with OOMPAH-815 accepted-branch and recovery-publication authority. A static review caught and repaired the composed project_id_val recovery-path NameError before testing. Authoritative epic-OOMPAH-768 will not be rewritten or pushed until OOMPAH-807 lands and combined tests pass.
---
<!-- COMMENTS:END -->
