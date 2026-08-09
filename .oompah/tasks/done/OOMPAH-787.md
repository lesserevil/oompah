---
id: OOMPAH-787
type: task
status: Done
priority: 1
title: Complete shadow/enforce rollout, upgrade compatibility, and operator documentation
parent: OOMPAH-771
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-798
labels: []
assignee: null
created_at: '2026-08-04T13:59:09.296051Z'
updated_at: '2026-08-09T21:14:55.492843Z'
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
    override_id: override-d472e4d1ac17
    project_id: proj-14849f1b
    task_id: OOMPAH-787
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0ff40928e793103d4bda7c4219046075ad1f771d4c30cd25c6574d8b7dbc84f1
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope and every prerequisite wave are contained in that validated
      head; owner override closes the composed work without fabricating a separate
      integration generation.
    created_at: '2026-08-08T16:31:43.457413+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-787
    target_state: Done
    evidence_fingerprint: 0ff40928e793103d4bda7c4219046075ad1f771d4c30cd25c6574d8b7dbc84f1
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:31:53.858051+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: 'Retain authoritative terminal provenance while OOMPAH-975 repairs null-head
      rollup transitions: this Done child was owner-accepted in the delivered systemic
      composition, and the current workflow job itself records exact immediate-target
      landing revision 33f85955b3c1285987253c2ff17b31f574c6d12f from this task into
      its canonical epic target. Do not rearm implementation.'
    marked_at: '2026-08-09T21:14:53.950461+00:00'
    updated_at: '2026-08-09T21:14:53.950461+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: 'Retain authoritative terminal provenance while OOMPAH-975 repairs null-head
        rollup transitions: this Done child was owner-accepted in the delivered systemic
        composition, and the current workflow job itself records exact immediate-target
        landing revision 33f85955b3c1285987253c2ff17b31f574c6d12f from this task into
        its canonical epic target. Do not rearm implementation.'
      recorded_at: '2026-08-09T21:14:53.950461+00:00'
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

Implement per-domain .env/.env.example rollout controls, persisted-schema migrations, startup compatibility, safe rollback before final flag retirement, canary health gates, and final enforcement/default cleanup. Update user docs for why-not-progressing, action_required alerts, recovery, SLOs, upgrade/rollback, and architecture; update plans with internal design and delete contradictory descriptions. Verify live canary and production-like soak before removing shadow/legacy flags. Acceptance: upgrade from current persisted state is automatic and restart-safe; rollback boundaries are documented/tested; final configuration has no obsolete toggles; operators no longer need manual task-state workarounds for recoverable conditions.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 08:02
---
Direct implementation started in isolated branch direct/OOMPAH-787-on-systemic at exact systemic base 6cbbd6ef7bb7882257c4c9e9175bd5b3edc14183. Auditing shipped rollout/config/schema/docs first; will implement only remaining gaps and return a tested local commit for composition.
---
author: oompah
created: 2026-08-08 08:30
---
Direct implementation complete on isolated branch direct/OOMPAH-787-on-systemic at 106df6c547e5cc30be989ffef36978ebd279c29b (base 6cbbd6ef7bb7882257c4c9e9175bd5b3edc14183). Added four per-domain .env rollout modes with safe aggregate ownership, restart-persistent qualification/soak gates and state projection, interrupted schema-migration recovery, a bounded make workflow-rollout-check canary, final flag compatibility/retirement rules, and operator/internal rollout, recovery, why-not-progressing, alert, SLO, upgrade/rollback, and architecture docs. Exact final focused broker run: 85 passed; prior expanded run: 174 passed. Pycompile, focused Ruff, git diff check, terminal mutation scan, and secret scan passed. Worktree is clean and preserved for composition; no task status or remote was changed.
---
author: oompah
created: 2026-08-08 16:31
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope and every prerequisite wave are contained in that validated head; owner override closes the composed work without fabricating a separate integration generation.
---
<!-- COMMENTS:END -->
