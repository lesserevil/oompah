---
id: OOMPAH-459
type: epic
status: Backlog
priority: 1
title: Route all terminal-state producers through independent auditing
parent: null
children:
- OOMPAH-476
- OOMPAH-477
- OOMPAH-478
- OOMPAH-479
- OOMPAH-480
- OOMPAH-481
- OOMPAH-482
- OOMPAH-483
blocked_by:
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:03:46.877390Z'
updated_at: '2026-07-28T13:09:05.263656Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Goal

Integrate the terminal-audit coordinator into every path that currently writes Done, Merged, or Archived so no agent, API, webhook, YOLO action, rollup, reconciler, or maintenance job can silently bypass validation.

Required behavior

- Agent and API requests for terminal status stage In Validation rather than writing the terminal status directly.
- Automatic Done, Merged, and Archived transitions use the same coordinator and target-specific audit contracts.
- A direct Merged observation chains completion and landing audits when required.
- Failed epic audits reopen the epic as Open with audit:repair-needed and permit one epic-planner repair run even when children already exist.
- A safety reconciliation pass detects terminal writes outside the coordinator while grandfathering the upgrade baseline.
- A static regression test rejects new direct terminal tracker mutations outside an explicit coordinator allowlist.
- Explicit authorized owner overrides remain available and auditable.

Constraints

Build on the foundation and auditor-dispatch epics. Preserve existing close, unpushed, CI, rebase, epic landing, and release gates as deterministic evidence inputs. Do not weaken status-label authorization. All code changes require tests.

Acceptance criteria

Every known terminal producer is covered by the coordinator, unaudited future terminal states are detected and staged, normal nonterminal behavior is unchanged, and focused integration tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

