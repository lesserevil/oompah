---
id: OOMPAH-919
type: bug
status: Done
priority: 1
title: Exclude paused projects from shadow rollout coverage failures
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T15:44:04.212180Z'
updated_at: '2026-08-09T21:43:13.019965Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-4d9e01306c26
    project_id: proj-14849f1b
    task_id: OOMPAH-919
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0f46b34c454b7b1f1a6861e1bc1cd67311f443c885cef158c3ddb8de19230183
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope is contained in that validated head; owner override avoids fabricating
      a separate branch/integration generation.
    created_at: '2026-08-08T16:28:25.635938+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-919
    target_state: Done
    evidence_fingerprint: 0f46b34c454b7b1f1a6861e1bc1cd67311f443c885cef158c3ddb8de19230183
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:28:34.605386+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Owner-reviewed terminal implementation is retained. The Done child is
      durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
      exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
    marked_at: '2026-08-09T21:43:11.531687+00:00'
    updated_at: '2026-08-09T21:43:11.531687+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Owner-reviewed terminal implementation is retained. The Done child is
        durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
        exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
      recorded_at: '2026-08-09T21:43:11.531687+00:00'
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

The live all-domain shadow rollout registers six managed projects but intentionally skips paused projects. WorkflowRuntime.reconcile currently treats every skipped binding as a coverage failure, so healthy active-project decisions can never accumulate a successful shadow sweep while any unrelated project is paused. Change oompah/workflow_runtime.py so rollout coverage is evaluated over enabled bindings only, while an empty enabled set still cannot qualify. Add a regression in tests/test_workflow_runtime.py with one enabled and one paused binding, asserting the paused project remains skipped and the active project produces a successful shadow sweep. Run focused tests and the exact full make test gate. Acceptance: paused projects neither mutate nor fail active-project rollout qualification; missing/error/incomplete enabled-project coverage still fails closed; the live rollout reaches qualification without unpausing unrelated projects.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 15:47
---
Live shadow rollout reproduced the bug on build 958fb98: two sweeps failed because paused unrelated projects were treated as missing active coverage. The direct owner fix now qualifies only enabled bindings while retaining a no-active-project fail-closed check. Focused serial regressions pass (3 tests).
---
author: oompah
created: 2026-08-08 16:28
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope is contained in that validated head; owner override avoids fabricating a separate branch/integration generation.
---
<!-- COMMENTS:END -->
