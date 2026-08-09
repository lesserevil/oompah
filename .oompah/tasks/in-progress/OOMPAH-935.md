---
id: OOMPAH-935
type: bug
status: In Progress
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
updated_at: '2026-08-09T07:43:12.463009Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
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
<!-- COMMENTS:END -->
