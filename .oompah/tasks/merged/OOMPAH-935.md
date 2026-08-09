---
id: OOMPAH-935
type: bug
status: Merged
priority: 1
title: Resolve legacy Done-child landing refreshes against immediate parent targets
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-09T07:21:24.754079Z'
updated_at: '2026-08-09T08:49:56.725814Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-52331f1a8822
    project_id: proj-14849f1b
    task_id: OOMPAH-935
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e48598f8331c88a99de6a4c3e779ec80dfdea0580af378fb27957acfc13c5277
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner direct delivery is on protected main at b7e7d950 after
      PR #750 and all hosted tests passed; live production reconciliation has proven
      immediate-parent landing for the OOMPAH-476 legacy cohort and is replacing stale
      generations.'
    created_at: '2026-08-09T08:49:52.658285+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-699

Problem: the all-enforce production rollout resumed a pre-existing durable batch and 86 integration_landing_refresh jobs exhausted. Legacy Done children such as OOMPAH-476 have parent epic metadata and an integrated queue receipt, but their tracker integration record lacks base_branch/integrated_sha. IntegrationWorkflowController and OrchestratorIntegrationActionBackend therefore build no exact landing request or fall back to main instead of the immediate parent epic branch, so valid historical landings can never be observed and retries exhaust. Scope: introduce one shared legacy-aware landing-request resolver used by the integration controller and action backend. Resolve source/revision from the tracker integration record with a durable integration-queue fallback; resolve target from integration.base_branch, queue.base_branch, then the parent issue work branch/canonical epic branch, using the project default only for unparented work. Preserve exact ancestry/patch-equivalence and fail-closed evidence rules. Relevant files: oompah/integration_workflow.py and supporting fact/controller code only as required. Tests: legacy Done child with null/generic target resolves its parent epic target rather than main; queue-only legacy integrated row supplies source/head; old exhausted wrong-target generation is superseded by exactly one corrected replacement across restart; unparented fallback remains the project target; focused integration/runtime/store tests. Acceptance: the production Done backlog reconciles without direct DB mutation, old exhausted rows remain immutable history but current exhaustion clears, repeated restart is idempotent, liveness reaches complete with zero current divergence, and the rollout gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 07:43
---
Direct-owner implementation complete at clean pushed head dec7e472ca653d5a35aa0ffba68a4f2e1c10947d. Legacy Done children now use durable integrated queue source revisions and immediate-parent targets; pruned parent refs are recovered only through an accepted final parent head plus fresh exact ancestry or complete non-empty git-cherry patch equivalence. Actual OOMPAH-476 has five of five equivalent patches against accepted parent head 95581aca. Verification: 191 affected tests passed plus focused negative cases; Ruff/diff checks clean. Awaiting combined protected-main integration with OOMPAH-936/OOMPAH-937.
---
author: oompah
created: 2026-08-09 08:31
---
Combined delivery is pushed at final head cafc100c4 on PR #750. Protected hosted CI is running the complete gate on Python 3.11, 3.12, and 3.13.
---
author: oompah
created: 2026-08-09 08:49
---
Delivered to protected main by merged PR #750 at b7e7d9509a4e6025b48c54336098acef2dda4986; complete hosted gates passed on Python 3.11/3.12/3.13. Live generation 246 proves the resolver against production legacy data: OOMPAH-476 through OOMPAH-480 now project terminal.immediate_target_landing_proven instead of landing_missing, stale generations were superseded, and current exhaustion fell from 128 to 104 while the recovery wave continues.
---
<!-- COMMENTS:END -->
