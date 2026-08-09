---
id: OOMPAH-953
type: bug
status: Open
priority: 1
title: Keep quality-gate cancellation polling local and bounded
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T11:17:05.346841Z'
updated_at: '2026-08-09T11:17:30.900018Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live OOMPAH-946 delivery made 197 GitHub branch-head requests from 11:04:00 through 11:09:51 while waiting for and running one exact branch gate. ValidationResourceLease.acquire polls is_cancelled every 50 ms and BranchQualityGate polls again every 100 ms, but the standalone callback calls _standalone_delivery_authorized, which invalidates/refetches the native task graph and invokes the remote head_resolver. Normal cancellation liveness therefore creates unbounded tracker/forge I/O, log volume, event-loop pressure, and rate-limit exposure. Scope: split a cheap local cancellation predicate (exact in-memory authority identity/revoked flag, workflow generation, and durable lease cancellation) from expensive full tracker/dependency/remote revalidation; use only the cheap predicate inside tight lease/gate loops; retain exact full tracker, dependency, and remote-head barriers immediately before snapshot/command spawn and after a passing result. Preserve prompt local revocation, exact-head fencing, stale workflow rejection, and fail-closed remote changes. Relevant code: oompah/validation_resource_lease.py acquire polling, oompah/quality_gate.py wait/run cancellation, oompah/orchestrator.py standalone delivery authority and gate callbacks. Required tests: hold validation capacity and run a gate while asserting tracker and remote resolver calls remain O(1); exact local revocation cancels promptly; workflow authority changes cancel; a remote head change before execution or after PASS is rejected; no stale review is created. Acceptance: cancellation latency remains bounded without network-backed hot polling, full exact revalidation still fences every external effect, focused lease/gate/standalone suites and terminal/secret scans pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

