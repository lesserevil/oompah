---
id: OOMPAH-489
type: task
status: Open
priority: 1
title: Validate nested epic auditing, repair planning, races, and cross-tracker behavior
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-452
- OOMPAH-478
- OOMPAH-482
- OOMPAH-483
- OOMPAH-488
labels: []
assignee: null
created_at: '2026-07-28T13:08:28.198709Z'
updated_at: '2026-07-28T18:07:36.380623Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Add end-to-end scenarios for a shared epic with several child contributors/models and a nested child epic. Prove the epic auditor excludes every contributing model, child In Validation blocks rollup, Done and Merged audits use the correct branch chain, and a failed epic audit reopens with audit:repair-needed for exactly one repair-planner run. Add races: evidence changes during audit, duplicate webhook plus polling merge signals, service restart with a running audit, no independent candidate, and authorized owner override. Run the same lifecycle contract against native Markdown and GitHub tracker fixtures, plus GitLab when its recovered adapter is present.

Tests

This task is the test implementation. Use deterministic clocks, fake providers, bare Git remotes, and fake SCM APIs; no external network. Run focused tests and make test.

Acceptance criteria

Nested/shared epic work cannot terminalize early, stale or duplicate results cannot win races, repair planning is idempotent, independence is enforced across contributors, and tracker adapters share the same externally visible lifecycle.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

