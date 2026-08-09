---
id: OOMPAH-940
type: epic
status: In Validation
priority: 1
title: Converge the legacy Done backlog from authoritative delivery evidence
parent: null
children:
- OOMPAH-941
- OOMPAH-942
- OOMPAH-943
- OOMPAH-944
- OOMPAH-945
- OOMPAH-954
- OOMPAH-955
- OOMPAH-956
- OOMPAH-958
- OOMPAH-960
- OOMPAH-961
- OOMPAH-962
blocked_by:
- OOMPAH-939
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:16.594615Z'
updated_at: '2026-08-09T14:35:22.515618Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-fddacbaa91fb
    project_id: proj-14849f1b
    task_id: OOMPAH-940
    digest: 0a8f66ccd7cf1de072dd1b0feb8ac319adc1bf49c227fd03ebf4eaf1970e9daa
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-fddacbaa91fb
    project_id: proj-14849f1b
    task_id: OOMPAH-940
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0a8f66ccd7cf1de072dd1b0feb8ac319adc1bf49c227fd03ebf4eaf1970e9daa
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: In Progress
    created_at: '2026-08-09T13:59:06.485551+00:00'
    selected_ref: origin/epic-OOMPAH-940
    selected_sha: 2dd74be288b81265ea4a242d7467ecc1ed9f1435
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-935 and OOMPAH-937\n\nThe live all-enforce rollout now has zero current liveness divergence, but 185 Oompah tasks remain in Done and generation 260 still reports 97 actionable exhausted jobs. Production evidence divides the residual backlog into independent authority gaps: authorized owner-delivery provenance is ignored, terminal parent branches were pruned without a trusted accepted-head fallback, successful landing refresh effects are not durably fed back, epic cleanup uses a separate child-proof path, and terminal transition guards can contradict an exact-current terminal work decision. Decompose and deliver the child bugs without direct database edits or broad status overrides.\n\nScope: make the workflow fact, action, transition, and cleanup paths share durable exact evidence and one current authority decision; preserve immutable history, bounded scheduling, pause semantics, and fail-closed behavior. Required rollout verification: complete scan, zero current divergence, zero current exhausted jobs or an explicitly non-task system owner, no repeated successful landing refreshes, no contradictory terminal guard decisions, and natural topology-safe movement of the legacy Done backlog. Required tests: focused unit/integration/restart regressions for each child plus complete protected branch gates and a live rollout canary. Acceptance: all children and OOMPAH-939 land; the Oompah project has no erroneously stuck non-terminal task and the workflow rollout check passes.

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
created: 2026-08-09 13:40
---
Refreshed the systemic workflow epic onto composition merge 91bf64c57 at exact branch head 2dd74be288b81265ea4a242d7467ecc1ed9f1435. Resolved the workflow-worker/runtime seams while preserving atomic landing completion, restart-safe transition finalization, exact containment authority, and canonical runtime fact composition. Validation: 159 workflow/runtime/finalization tests, 202 integration/epic/decision tests, 8 targeted composed-seam tests, and terminal mutation scan all passed. PR #757 hosted matrix is refreshing; a final small main refresh will follow OOMPAH-957.
---
author: oompah
created: 2026-08-09 13:59
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 13:59
---
Completed and merged systemic workflow convergence via PR #757 at ba0859da9. All child fixes are contained; Python 3.11/3.12/3.13 hosted gates passed, 369 focused composition tests and terminal scan passed, and independent semantic review found no blockers. Live rollout verification is running on the deployed exact merge.
---
<!-- COMMENTS:END -->
