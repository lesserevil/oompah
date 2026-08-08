---
id: OOMPAH-797
type: task
status: In Progress
priority: 1
title: Qualify the workflow engine with a multi-project 100-task soak
parent: OOMPAH-767
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-792
- OOMPAH-796
- OOMPAH-805
labels: []
assignee: null
created_at: '2026-08-04T13:59:28.518646Z'
updated_at: '2026-08-08T12:03:15.322156Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Build a deterministic production-like workload with at least 100 tasks across projects, independent tasks, shared/nested epics, cross-epic dependencies, reviews, audits, retries, branch pruning, and injected transient failures. Measure liveness SLOs, fairness, queue age, job retries, restart reconstruction, decision/UI parity, memory/SQLite growth, and alert actionability. Integrate a bounded version into CI and retain a longer operator soak target. Acceptance: all recoverable work reaches terminal state without manual intervention, only deliberately unrecoverable cases escalate, no task remains unexplained, and resource use stays within documented bounds.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 07:52
---
Direct implementation started in isolated worktree based exactly on systemic head 6cbbd6ef7bb7882257c4c9e9175bd5b3edc14183. Scope: deterministic >=100-task multi-project soak harness, bounded CI target, longer operator target/docs, and assertions for liveness/fairness/retries/restart/UI/resource/alerts. Focused validation will use the shared dedicated broker.
---
author: oompah
created: 2026-08-08 08:04
---
Implementation complete on isolated branch direct/OOMPAH-797-on-systemic at 20d88afc6fed8aa21381a2a2af6140a1f70f336a (base 6cbbd6ef7bb7882257c4c9e9175bd5b3edc14183). Added deterministic production-component workflow soak with 104-task pytest CI coverage, 120-task make workflow-soak-ci target, 1000-task make workflow-soak operator target, restart/fairness/retry/projection/alert/resource assertions, and operator docs/.env tuning. Dedicated focused broker: 40 passed in 4.55s; artifact /home/shedwards/.oompah/ci-artifacts.OOMPAH-797-rerun.soPL3G. Secret scan, terminal-mutation scan, diff check, and worktree cleanliness passed. Worktree preserved for composition.
---
<!-- COMMENTS:END -->
