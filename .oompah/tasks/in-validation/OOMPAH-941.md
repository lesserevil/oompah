---
id: OOMPAH-941
type: bug
status: In Validation
priority: 1
title: Project authorized owner delivery before requiring landing recovery
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:20.700706Z'
updated_at: '2026-08-09T12:52:32.281945Z'
work_branch: OOMPAH-941
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-941
  base_branch: epic-OOMPAH-940
  base_sha: b7e7d9509a4e6025b48c54336098acef2dda4986
  head_sha: 9996c0f8e8b64d83ee59bd65d3552f034df6031a
  submitted_at: '2026-08-09T09:45:24.452634+00:00'
  updated_at: '2026-08-09T09:45:24.452634+00:00'
oompah.work_branch: OOMPAH-941
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-aec6dc669619
    project_id: proj-14849f1b
    task_id: OOMPAH-941
    digest: 33b6bc646cffb9ddb9cf92ed12548373f29912c4e39c70fe4c34dd54ba065b20
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-aec6dc669619
    project_id: proj-14849f1b
    task_id: OOMPAH-941
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 33b6bc646cffb9ddb9cf92ed12548373f29912c4e39c70fe4c34dd54ba065b20
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Ready to Integrate
    created_at: '2026-08-09T12:52:25.456900+00:00'
    selected_ref: 9996c0f8e8b64d83ee59bd65d3552f034df6031a
    selected_sha: 9996c0f8e8b64d83ee59bd65d3552f034df6031a
  attempt_history: []
---
## Summary

Production generation 260 leaves 73 owner-overridden Done tasks in landing_missing/evidence_unknown/retry.exhausted because their accepted project-owner terminal provenance is not represented in canonical delivery facts. Scope: collect only authorized, revision-bound owner terminal provenance that actually proves delivery to the configured target; project it before scheduling integration_landing_refresh; do not treat a generic Done status, comment, or unbound override as merge evidence. Relevant code: terminal transition provenance/audit metadata, workflow fact collection, integration work decisions, restart persistence. Tests: valid owner delivery with exact accepted revision becomes terminal without a landing job; unbound/wrong-target/stale/malformed override remains fail-closed; restart parity and superseded history. Acceptance: qualifying live rows leave current exhaustion naturally, non-qualifying rows remain actionable, and complete gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 09:10
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
author: oompah
created: 2026-08-09 09:43
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-941`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`
Process: ended without subprocess exit evidence

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
author: oompah
created: 2026-08-09 09:43
---
Implemented exact revision binding for project-owner terminal overrides and fail-closed owner-delivery landing facts. Added wrong-target, stale, malformed, unauthorized, supersession, and restart regression coverage. Focused suite: 414 passed. Branch OOMPAH-941 is pushed at e5df74c13292aefa564436995aa506a4592f11e9; PR #752 has auto-merge enabled and is awaiting CI.
---
author: oompah
created: 2026-08-09 09:43
---
Revision-bound authorized owner delivery now becomes canonical landing evidence before landing recovery; non-qualifying provenance remains actionable. Focused checks passed and PR #752 is queued for auto-merge.
---
author: oompah
created: 2026-08-09 09:45
---
Corrected delivery target to epic-OOMPAH-940 and republished exact head 9996c0f8e8b64d83ee59bd65d3552f034df6031a. Revision-bound owner-delivery implementation and 414 focused tests are ready for the normal integration gate.
---
author: oompah
created: 2026-08-09 12:52
---
Reconciled the in-flight integration deadlock: the accepted task commits are authoritatively contained in origin/epic-OOMPAH-940, so the exhausted administrative integration job is obsolete. Advancing to terminal validation while OOMPAH-958 fixes the systemic lease contract.
---
author: oompah
created: 2026-08-09 12:52
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
