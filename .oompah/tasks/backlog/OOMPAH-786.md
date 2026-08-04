---
id: OOMPAH-786
type: feature
status: Backlog
priority: 1
title: Implement versioned WorkflowFacts and first-class LandingFact
parent: OOMPAH-765
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:59:07.630785Z'
updated_at: '2026-08-04T13:59:07.630785Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Define immutable/versioned facts for task snapshots, dependency/containment graph, integration row and record, terminal audit chain, review/CI, Git/forge landing, implementation/owner authority, retry budgets, and relevant config. Introduce LandingFact(source,target,revision,proof,observed_at,evidence_revision) with positive/negative/unknown distinctions and durable proof handling after branch deletion. Build project-scoped collectors with explicit stale/error facts rather than false empty results. Required tests: deterministic revisions, missing/error/stale inputs, patch/ancestry evidence, deleted branches, nested targets, cross-project isolation, and serialization compatibility. Acceptance: all evidence used by progression can be expressed without consulting ad hoc global state or inferring landing from parent status.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

