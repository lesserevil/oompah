---
id: OOMPAH-947
type: task
status: In Progress
priority: null
title: Bound terminal-audit lane cost beyond candidate count
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:38:30.732911Z'
updated_at: '2026-08-09T10:15:21.815634Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression after completed OOMPAH-809 on main b7e7d950: scheduler generation 285 processed the configured 32-candidate audit window but terminal_audit.audit_scan/audit_dispatch still consumed about 298 seconds and the complete tick consumed 411.7 seconds across 945 Oompah issues. During that interval newly submitted OOMPAH-942/944/945 integration work remained Ready without prompt claims and the published state snapshot became stale. The candidate-count window is bounded, but sequential metadata, selector preparation, revision binding, recovery, and health work inside each candidate can still make one lane consume minutes. Scope: measure and bound the full audit-lane unit of work with a durable fair cursor and explicit per-tick operation/time budget; cache or batch project-scoped selector/config authority where safe; separate prompt launch/finalization work from complete health observation so partial scans remain truthful without blocking integration/dispatch; request an immediate coalesced continuation while work remains. Preserve exact audit ownership, independent candidate selection, terminal transition fencing, project fairness/pause semantics, immutable history, and fail-closed errors. Relevant code: Orchestrator._dispatch_audit_lane, _audit_candidate_window, _prepare_audit_selector, metadata reads, terminal-audit health generation, and scheduler event continuation. Required tests: hundreds of candidates with individually slow selector/metadata sources keep every lane invocation below its deterministic budget; a Ready integration claim progresses during the sliced scan; cursors survive restart and visit every project/task fairly; finalizations remain prompt; partial health cuts never claim complete/healthy; continuation coalesces; no duplicate auditor launch across slices. Acceptance: the live Oompah project audit phase is bounded to a scheduler-scale interval rather than minutes, submitted integration work starts promptly under backlog, complete focused/full gates pass, and rollout telemetry demonstrates fair convergence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 10:15
---
Implemented bounded terminal-audit slicing: project-fair durable cursor rotation, configurable candidate-operation and runtime budgets, time-bounded read-only preparation, per-lane selector authority caching, coalesced continuation, and cross-slice truthful health completion while finalizations and fenced mutations retain exact ownership. Focused validation is green: 314 audit/config/orchestrator tests passed; the wider audit caller suite previously passed 636 tests with one pre-existing AsyncMock warning. Preparing the exact reviewed head for submission.
---
<!-- COMMENTS:END -->
