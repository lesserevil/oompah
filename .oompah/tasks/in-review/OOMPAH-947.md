---
id: OOMPAH-947
type: task
status: In Review
priority: null
title: Bound terminal-audit lane cost beyond candidate count
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:38:30.732911Z'
updated_at: '2026-08-09T11:56:03.443710Z'
work_branch: OOMPAH-947
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/760
review_number: '760'
review_head: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-947
  head_sha: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
  submitted_at: '2026-08-09T10:16:03.848211+00:00'
  updated_at: '2026-08-09T10:16:03.848211+00:00'
oompah.work_branch: OOMPAH-947
oompah.review_url: https://github.com/lesserevil/oompah/pull/760
oompah.review_number: '760'
oompah.target_branch: main
oompah.review_head: 139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5
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
author: oompah
created: 2026-08-09 10:16
---
Bound terminal-audit lane cost with project-fair durable cursor slicing, 8-operation/15-second configurable budgets, time-bounded read-only preparation, per-lane selector authority caching, coalesced continuations, and truthful cross-slice health convergence. Finalizations and fenced mutations remain prompt and uncancelled. Validation: 314 focused audit/config/restart tests passed; wider audit caller suite 636 passed with one pre-existing AsyncMock warning.
---
author: oompah
created: 2026-08-09 11:55
---
Branch quality gate passed for `139a848cfbf8dfa605a9033a5b1dde3a3c1c84a5` using `make test` in 166.7s. Review creation may proceed.
---
<!-- COMMENTS:END -->
