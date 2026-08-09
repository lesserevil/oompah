---
id: OOMPAH-928
type: bug
status: Done
priority: 1
title: Bound epic restart cleanup seeding and aggregate historical uncertainty
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T23:09:00.912201Z'
updated_at: '2026-08-09T20:16:39.510716Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-94d64915c9de
    project_id: proj-14849f1b
    task_id: OOMPAH-928
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fa0d5947889ae7b6d9c00e8a93d1aacdfd75811922deac0e47d51804854ad3d2
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:14:14.123841+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-928
    target_state: Done
    evidence_fingerprint: fa0d5947889ae7b6d9c00e8a93d1aacdfd75811922deac0e47d51804854ad3d2
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:14:31.228540+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Project owner confirms OOMPAH-928 is a completed historical/provenance-only
      legacy record; this is not a landing claim.
    marked_at: '2026-08-09T20:16:37.334140+00:00'
    updated_at: '2026-08-09T20:16:37.334140+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Project owner confirms OOMPAH-928 is a completed historical/provenance-only
        legacy record; this is not a landing claim.
      recorded_at: '2026-08-09T20:16:37.334140+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-763

All-enforce restart on ce8b839811c2f0ff297179278aa3aa6171c5705b scanned 126 epics and emitted 86 one-per-task WARNING records for historical Merged/Archived epics whose already-pruned source generation is legitimately unavailable. The restart seed in oompah/epic_workflow_adapter.py schedules CLEANUP for every terminal epic, performs serialized tracker/forge/Git fact work, increments its scheduled count even when _schedule defers without enqueuing, and treats expected historical cleanup uncertainty as individually actionable. Refactor restart seeding to keep current retained cleanup authority fail-closed while avoiding unnecessary historical terminal cleanup work where absence is proven, make scheduling counts reflect actual enqueues, demote/suppress non-actionable per-epic noise, and emit at most one bounded aggregate startup summary. Add regression tests covering mixed current/historical terminal epics, exact-generation absence, actual retained cleanup failures, count accuracy, bounded log cardinality/severity, and idempotent restart behavior. Run focused epic workflow adapter tests and the complete make test gate. Acceptance: restart does not emit one warning per safely pruned historical epic; actionable retained cleanup uncertainty remains visible; reported counts equal durable jobs actually scheduled; startup work is bounded and does not create duplicate cleanup jobs.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 23:35
---
Implementation complete in the shared candidate worktree: restart cleanup seeding now counts only newly created durable jobs, is stable across runtime owner/process restarts, avoids collector/Git work for terminal epics without tracker exact heads, classifies retained durable cleanup authority, and emits exactly one bounded aggregate summary per seed pass. Focused epic workflow and adapter suite: 81 passed. Awaiting integration with OOMPAH-927 and the exact full branch gate.
---
author: oompah
created: 2026-08-09 05:14
---
Direct project-owner completion verified on composed rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e: exact full gate passed (18,874 passed, 7 skipped, 2 xfailed), all four durable workflow domains are live in enforce mode, no actionable global alerts remain, and current durable exhaustion/expired leases are zero.
---
author: oompah
created: 2026-08-09 05:14
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct project-owner completion after exact-head full-gate and live enforce verification.
---
<!-- COMMENTS:END -->
