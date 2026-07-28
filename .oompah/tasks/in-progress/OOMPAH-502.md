---
id: OOMPAH-502
type: epic
status: In Progress
priority: 1
title: Reduce agent wall-clock latency without weakening delivery gates
parent: null
children:
- OOMPAH-503
- OOMPAH-504
- OOMPAH-505
- OOMPAH-506
- OOMPAH-507
- OOMPAH-508
- OOMPAH-509
- OOMPAH-510
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:03:45.331314Z'
updated_at: '2026-07-28T15:10:28.970213Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-501

Objective: reduce time spent in duplicate screening, prompt replay, repeated branch-wide tests, provider ambiguity, restart recovery, and stale storage while preserving one-writer-per-shared-epic and the rule that a PR/MR is created only when the entire branch is ready.

Scope: auto duplicate detection compares only nonterminal tasks; agent prompts retain the latest actionable human context and focus handoff without replaying unbounded history; Claude and Codex role candidates use explicit fast/standard/deep models; managed stale caches and worktrees receive a daily scan plus earlier pressure-triggered cleanup; deployment restarts drain active agents before replacing the process; intermediate focus handoffs use focused tests while one branch-ready gate runs the full suite; and pytest parallelism is enabled only after isolation is proven.

Constraints: keep all tunables in .env/.env.example, preserve provider round-robin and one-agent-per-epic safety, never delete active/unowned paths, never weaken terminal audit or merge readiness, and create no rollup PR/MR until every child is Done with landing evidence.

Acceptance criteria: each child has regression tests and operator documentation; the final clean branch passes make test and the secret scan; measured dispatch/task timing shows removed redundant work; cleanup is observable and fail-safe; role telemetry records the explicit provider/model; a single epic-owned review is created only after the full branch is ready.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

