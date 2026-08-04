---
id: OOMPAH-775
type: task
status: Open
priority: 1
title: Route API and auxiliary status writes through TaskTransitionService and enforce
  the boundary
parent: OOMPAH-769
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-776
labels: []
assignee: null
created_at: '2026-08-04T13:58:48.205609Z'
updated_at: '2026-08-04T21:22:46.370923Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Migrate server API/CLI handoff paths, stalled_task_watchdog, terminal_audit_enforcement, ACP tools, intake bridges, project maintenance, and remaining production modules to TaskTransitionService. Retain tracker adapter implementations but forbid direct production status calls with an AST/static architectural test and terminal-audit scan integration. Preserve authenticated principal/owner rules and response compatibility. Required tests: REST/CLI transitions, actor mismatch, owner claim, intake promotion, Needs Human instructions, terminal aliases, auxiliary recovery, and architectural boundary violations. Acceptance: only TaskTransitionService and tracker adapters may write status; every transition is journaled and reason-coded.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:22
---
Prerequisite OOMPAH-776 is Done and the later duplicate OOMPAH-803 has been archived. Promoting the canonical task so the server can dispatch the remaining OOMPAH-769 boundary work.
---
<!-- COMMENTS:END -->
