---
id: OOMPAH-786
type: feature
status: In Progress
priority: 1
title: Implement versioned WorkflowFacts and first-class LandingFact
parent: OOMPAH-765
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-772
labels: []
assignee: null
created_at: '2026-08-04T13:59:07.630785Z'
updated_at: '2026-08-04T15:12:24.311404Z'
work_branch: epic-OOMPAH-765--task-OOMPAH-786
target_branch: epic-OOMPAH-765
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.target_branch: epic-OOMPAH-765
oompah.work_branch: epic-OOMPAH-765--task-OOMPAH-786
---
## Summary

Define immutable/versioned facts for task snapshots, dependency/containment graph, integration row and record, terminal audit chain, review/CI, Git/forge landing, implementation/owner authority, retry budgets, and relevant config. Introduce LandingFact(source,target,revision,proof,observed_at,evidence_revision) with positive/negative/unknown distinctions and durable proof handling after branch deletion. Build project-scoped collectors with explicit stale/error facts rather than false empty results. Required tests: deterministic revisions, missing/error/stale inputs, patch/ancestry evidence, deleted branches, nested targets, cross-project isolation, and serialization compatibility. Acceptance: all evidence used by progression can be expressed without consulting ad hoc global state or inferring landing from parent status.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 15:12
---
Implementation complete on the private task branch: added immutable WorkflowFacts with required task/dependency/containment/integration/audit/review/landing/authority/retry/config domains; explicit known/missing/stale/error observations; semantic evidence revisions that exclude poll timestamps and order churn; project-scoped collection with redacted stable provider failures; first-class project-fenced LandingFact; and a real Git collector that distinguishes landed/not-landed/unknown, proves deleted refs from exact revisions, preserves durable historical proof, and evaluates nested work on its immediate target. The 116 fact/incident/contract/reason/integration tests passed, the final 33 focused tests passed, and Ruff/format/diff/secret/terminal-mutation checks are clean.
---
<!-- COMMENTS:END -->
