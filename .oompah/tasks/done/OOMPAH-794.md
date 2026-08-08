---
id: OOMPAH-794
type: task
status: Done
priority: 1
title: Delete superseded reconcilers, watchdog heuristics, and duplicate workflow
  predicates
parent: OOMPAH-771
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-797
- OOMPAH-795
labels: []
assignee: null
created_at: '2026-08-04T13:59:23.320051Z'
updated_at: '2026-08-08T16:31:18.861544Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-88f928aaf4e4
    project_id: proj-14849f1b
    task_id: OOMPAH-794
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2a08f2f770a1e58ef1aac5a7ccc67a8418c2c18ebc661fe5bcd610db7a0139ea
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope and its completed dependency wave are contained in that validated
      head; owner override avoids fabricating a separate branch/integration generation.
    created_at: '2026-08-08T16:31:08.862530+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-794
    target_state: Done
    evidence_fingerprint: 2a08f2f770a1e58ef1aac5a7ccc67a8418c2c18ebc661fe5bcd610db7a0139ea
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:31:16.649998+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

After domain enforcement and soak gates, remove legacy eligibility summaries, direct status writers, read-time repair side effects, status-specific watchdog remediation, old integration/audit/review/epic reconcilers, obsolete process-local authority/cooldown maps, and fire-and-forget lifecycle futures. Retain only non-lifecycle housekeeping maintenance. Add architectural tests preventing reintroduction. Required tests: full make test, API compatibility, upgrade/restart with legacy persisted state, and WorkDecision parity. Acceptance: no dual workflow path remains; legacy deletion is measured and production workflow LOC/branch complexity decline materially.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 09:20
---
Independent implementation complete for composition: commit 31710c44741fca893d0b1663c83378defaa5a9f4 on direct/OOMPAH-794-on-systemic, based on e48d953e45e9e39933d86b46bf0b11faedd6a008. Runtime installation is now a one-way lifecycle authority boundary; legacy startup/tick/refresh/retry fallbacks cannot run in off/shadow. Focused high-risk suites passed (314 authority-fallback, 163 restart/event, final 16 regression); terminal mutation scan passed. Full broker: 18,557 passed with 16 unrelated composed-head failures. No push or status change performed.
---
author: oompah
created: 2026-08-08 16:31
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope and its completed dependency wave are contained in that validated head; owner override avoids fabricating a separate branch/integration generation.
---
<!-- COMMENTS:END -->
