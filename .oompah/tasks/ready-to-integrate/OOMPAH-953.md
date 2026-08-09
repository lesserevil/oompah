---
id: OOMPAH-953
type: bug
status: Ready to Integrate
priority: 1
title: Keep quality-gate cancellation polling local and bounded
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T11:17:05.346841Z'
updated_at: '2026-08-09T12:31:26.281549Z'
work_branch: OOMPAH-953
target_branch: null
review_url: https://github.com/lesserevil/oompah/pull/764
review_number: '764'
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-953
  head_sha: 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c
  submitted_at: '2026-08-09T11:37:01.843657+00:00'
  updated_at: '2026-08-09T11:37:01.843657+00:00'
oompah.work_branch: OOMPAH-953
oompah.review_url: https://github.com/lesserevil/oompah/pull/764
oompah.review_number: '764'
---
## Summary

Live OOMPAH-946 delivery made 197 GitHub branch-head requests from 11:04:00 through 11:09:51 while waiting for and running one exact branch gate. ValidationResourceLease.acquire polls is_cancelled every 50 ms and BranchQualityGate polls again every 100 ms, but the standalone callback calls _standalone_delivery_authorized, which invalidates/refetches the native task graph and invokes the remote head_resolver. Normal cancellation liveness therefore creates unbounded tracker/forge I/O, log volume, event-loop pressure, and rate-limit exposure. Scope: split a cheap local cancellation predicate (exact in-memory authority identity/revoked flag, workflow generation, and durable lease cancellation) from expensive full tracker/dependency/remote revalidation; use only the cheap predicate inside tight lease/gate loops; retain exact full tracker, dependency, and remote-head barriers immediately before snapshot/command spawn and after a passing result. Preserve prompt local revocation, exact-head fencing, stale workflow rejection, and fail-closed remote changes. Relevant code: oompah/validation_resource_lease.py acquire polling, oompah/quality_gate.py wait/run cancellation, oompah/orchestrator.py standalone delivery authority and gate callbacks. Required tests: hold validation capacity and run a gate while asserting tracker and remote resolver calls remain O(1); exact local revocation cancels promptly; workflow authority changes cancel; a remote head change before execution or after PASS is rejected; no stale review is created. Acceptance: cancellation latency remains bounded without network-backed hot polling, full exact revalidation still fences every external effect, focused lease/gate/standalone suites and terminal/secret scans pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 11:36
---
Implemented the local/full quality-gate authority split in the isolated OOMPAH-953 worktree. Tight 50/100ms lease/process loops now use exact local/workflow cancellation only; full tracker, dependency, project, and remote-head CAS checks run at pre-snapshot, pre-spawn, post-PASS, and the caller's final review boundary. Deterministic tests prove zero full reads while capacity-blocked and exactly three across execution, prompt local cancellation, workflow generation loss without graph I/O, and existing force-push/no-stale-review fences. Validation so far: 776 focused quality-gate/standalone/lease tests + 175 integration workflow/worker/recovery tests pass; terminal status mutation scan and secret scan pass. Awaiting independent no-blocker review before commit/submit.
---
author: oompah
created: 2026-08-09 11:36
---
Independent review found no blockers. Reviewed commit 20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c is pushed on origin/OOMPAH-953. Focused validation: 776 quality-gate/standalone/validation-lease tests and 175 integration-workflow/worker/delivery-recovery tests passed; terminal task-status mutation scan and secret scan passed.
---
author: oompah
created: 2026-08-09 11:37
---
Separated hot quality-gate cancellation polling from full tracker/dependency/remote revalidation, retained exact external-effect barriers, and added deterministic bounded-I/O and prompt-revocation coverage.
---
author: oompah
created: 2026-08-09 12:31
---
Branch quality gate passed for `20ab5659fd0a2bc67c5d31577f3a9e969eb1df7c` using `make test` in 160.1s. Review creation may proceed.
---
<!-- COMMENTS:END -->
