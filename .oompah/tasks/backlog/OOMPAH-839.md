---
id: OOMPAH-839
type: bug
status: Backlog
priority: 1
title: Classify and preserve externally terminated quality-gate outcomes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:49:04.553399Z'
updated_at: '2026-08-05T16:49:04.553399Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Forensic gap exposed by OOMPAH-523: its persisted exact BranchQualityGate result ended after 48.94 seconds at 9% pytest progress with only PASS lines and no pytest summary, make diagnostic, xdist crash, OOM event, service restart, or Oompah cancellation log. QualityGateResult and quality_gates.json omit the raw subprocess return code/terminating signal/owner generation, and BranchQualityGate maps every unmarked nonzero process return to cached status=failed. An externally SIGTERM/SIGKILL-terminated whole gate can therefore be cached as a product CI failure, moved to Needs CI Fix, and replayed indefinitely. Implementation scope: capture bounded structured exit evidence (return code, signal when negative, exact QualityGateOwner/generation, interrupted marker/source); distinguish genuine command exit 1 from external signal/runner infrastructure termination; make non-product infrastructure outcomes retryable and non-poisoning while preserving exact-owner cancellation semantics and sanitizing output. Relevant files: oompah/quality_gate.py, oompah/integration_executor.py, integration failure routing/observability, quality gate cache schema/compatibility. Required tests: genuine exit 1 caches failed; external SIGTERM and SIGKILL classify interrupted/infrastructure with evidence and do not poison a later exact retry; owner cancellation remains interrupted; timeout remains timed_out; restart reads old cache safely; UI/operator message is truthful. Acceptance: every cached gate outcome explains whether tests failed or infrastructure terminated the process, and signal-only exits cannot place a clean task in Needs CI Fix or replay as a product failure.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

