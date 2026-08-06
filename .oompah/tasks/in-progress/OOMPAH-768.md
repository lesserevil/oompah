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
updated_at: '2026-08-06T12:38:44.245979Z'
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
author: oompah
created: 2026-08-05 16:32
---
Integration checkpoint advanced: OOMPAH-807 passed the combined-tree gate and integrated at b1c089614. The refreshed OOMPAH-768 composition is based on that exact root and contains only the accepted durable integration/implementation/review plus OOMPAH-813 authority fixes; two conflict-repair corrections normalize project identity and preserve OOMPAH-815 recovery scope. Static checks are clean. Focused composition tests are intentionally waiting for the single shared validation lane, currently occupied by OOMPAH-523's legitimate make test; no duplicate test load is being introduced.
---
author: oompah
created: 2026-08-06 00:15
---
Critical-path parent rebase completed while dispatch was paused. epic-OOMPAH-768 was rebased from ce2526a8b7e67426c3919cf890a9b3b1cdca20ad onto exact epic-OOMPAH-763 head 58ffd477b19f370c7ed53a191e1a05580b016c85 and pushed at 16d83ea3eaf409338cc22449e1447be088bea7df. Upstream-equivalent OOMPAH-805/819 patches dropped naturally; OOMPAH-813 conflicts were combined with the newer root recovery fences, including exact scoped project identity. Verification: 489 focused workflow, submission, review, integration, long-tick, and terminal-transition tests passed; pycompile, diff check, and make check-secrets passed. OOMPAH-807 code is now reachable on this parent.
---
<!-- COMMENTS:END -->
