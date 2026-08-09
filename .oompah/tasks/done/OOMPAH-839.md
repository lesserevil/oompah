---
id: OOMPAH-839
type: bug
status: Done
priority: 1
title: Classify and preserve externally terminated quality-gate outcomes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:49:04.553399Z'
updated_at: '2026-08-09T05:09:23.198487Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-be1b453f3fe9
    project_id: proj-14849f1b
    task_id: OOMPAH-839
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2b8fbe1fce4d88ef626525d9c673b75fe7c59e9095c2cdb586c312b65461a55d
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:09:13.826506+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-839
    target_state: Done
    evidence_fingerprint: 2b8fbe1fce4d88ef626525d9c673b75fe7c59e9095c2cdb586c312b65461a55d
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:09:21.773940+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Forensic gap exposed by OOMPAH-523: its persisted exact BranchQualityGate result ended after 48.94 seconds at 9% pytest progress with only PASS lines and no pytest summary, make diagnostic, xdist crash, OOM event, service restart, or Oompah cancellation log. QualityGateResult and quality_gates.json omit the raw subprocess return code/terminating signal/owner generation, and BranchQualityGate maps every unmarked nonzero process return to cached status=failed. An externally SIGTERM/SIGKILL-terminated whole gate can therefore be cached as a product CI failure, moved to Needs CI Fix, and replayed indefinitely. Implementation scope: capture bounded structured exit evidence (return code, signal when negative, exact QualityGateOwner/generation, interrupted marker/source); distinguish genuine command exit 1 from external signal/runner infrastructure termination; make non-product infrastructure outcomes retryable and non-poisoning while preserving exact-owner cancellation semantics and sanitizing output. Relevant files: oompah/quality_gate.py, oompah/integration_executor.py, integration failure routing/observability, quality gate cache schema/compatibility. Required tests: genuine exit 1 caches failed; external SIGTERM and SIGKILL classify interrupted/infrastructure with evidence and do not poison a later exact retry; owner cancellation remains interrupted; timeout remains timed_out; restart reads old cache safely; UI/operator message is truthful. Acceptance: every cached gate outcome explains whether tests failed or infrastructure terminated the process, and signal-only exits cannot place a clean task in Needs CI Fix or replay as a product failure.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 05:09
---
Direct project-owner completion verified on composed rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e: exact full gate passed (18,874 passed, 7 skipped, 2 xfailed), all four durable workflow domains are live in enforce mode, no actionable global alerts remain, and current durable exhaustion/expired leases are zero.
---
author: oompah
created: 2026-08-09 05:09
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct project-owner completion after exact-head full-gate and live enforce verification.
---
<!-- COMMENTS:END -->
