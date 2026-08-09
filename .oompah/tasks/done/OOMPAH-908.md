---
id: OOMPAH-908
type: task
status: Done
priority: null
title: Give the whole-corpus dispatch contract scan a load-safe deadline
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T07:51:47.950793Z'
updated_at: '2026-08-09T05:10:52.062902Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-3679bf157b81
    project_id: proj-14849f1b
    task_id: OOMPAH-908
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 31932fc9ada16b5f9ac603521870910a3abce420c11117937ee949e0c73ff669
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:10:41.726355+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-908
    target_state: Done
    evidence_fingerprint: 31932fc9ada16b5f9ac603521870910a3abce420c11117937ee949e0c73ff669
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:10:50.498426+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Recurrence after completed OOMPAH-851 on exact systemic head 6cbbd6ef7: the full make test gate passed 18,485 tests and then tests/test_tick_dispatch_mock_contract.py::test_tick_dispatch_replacements_use_faithful_helper hit the global 5-second timeout while walking an unrelated module AST under saturated xdist load. There was no contract violation; the architectural scan is deliberately whole-corpus and its runtime grows with the test tree. Implementation scope: give this bounded corpus-wide architectural test a deterministic scoped deadline appropriate for saturated full gates, or further optimize the fail-closed prefilter without weakening direct, dynamic, decoded f-string, arbitrary split-string, malformed-source, helper-shadow, or missing-import detection. Do not change the global timeout or production telemetry. Required tests: exact architectural module repeatedly and under xdist/load, retain all fail-closed prefilter regressions, and rerun the exact full make test gate on the repaired composed head. Acceptance: the corpus scan cannot fail solely because the host is saturated, still reports every forbidden _handle_dispatch_needed replacement, and no global timeout is widened.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 05:10
---
Direct project-owner completion verified on composed rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e: exact full gate passed (18,874 passed, 7 skipped, 2 xfailed), all four durable workflow domains are live in enforce mode, no actionable global alerts remain, and current durable exhaustion/expired leases are zero.
---
author: oompah
created: 2026-08-09 05:10
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct project-owner completion after exact-head full-gate and live enforce verification.
---
<!-- COMMENTS:END -->
