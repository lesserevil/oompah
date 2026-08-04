---
id: OOMPAH-757
type: bug
status: Open
priority: 1
title: Persist canonical child landing evidence through conflict-resolved epic rebases
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:11:32.097478Z'
updated_at: '2026-08-04T11:12:34.804315Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0573b37ff17b0c122b129b6a275735dc1ff12972ba88bd0ebb35fbda1b011277
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: a6b3c663-f92c-4a05-bc27-f427dcfc8319
  claim_owner: bb82706b-fb95-42cd-a68d-43d670f815c6
  claimed_at: '2026-08-04T11:12:15.186273+00:00'
  claim_expires_at: '2026-08-04T11:42:15.186273+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 0021a13a-33cc-42a5-9a34-2df7be1ee15f
---
## Summary

Triggered by: EXOCOMP-130

Regression/incomplete implementation of OOMPAH-747 on live revision 5368e236. EXOCOMP-130 is audited Done but cannot open its nested-epic review into epic-EXOCOMP-127 because every scheduler pass reports EXOCOMP-148 as two unlanded commits, including 4e013110. The original child record is base eaeeaf08, head/integrated SHA 8400a54a. A prior authorized epic recovery preserved that branch and rebased its documentation and EventOutbox implementation into canonical epic commits 61141cb8 and 9663f4b2; origin/epic-EXOCOMP-130 currently contains those commits at head 7bf5506c. Conflict resolution combined configuration changes, so raw patch IDs differ and git cherry still reports +8400a54a. OOMPAH-747 only accepts exact ancestry/patch equivalence or Oompah-authored child completion SHAs; it does not persist or consume structured conflict-resolved rebase mappings from the authorized epic-rebase helper. The live system therefore repeats a fail-closed diagnostic forever, has no recovery owner, and blocks EXOCOMP-130, parent EXOCOMP-127, and cross-epic dependents such as EXOCOMP-152/160/180. Implementation scope: when an authorized direct epic-maintenance rebase rewrites child ranges and resolves conflicts, persist structured canonical landing evidence per affected child (old base/head/range, new canonical range/head, target epic branch, rebase helper/task, exact pre/post refs, validation result, and evidence fingerprint); consume only current, complete, service-authored evidence in _child_landing_evidence_block_reason and review readiness; provide a bounded historical repair path for the exact EXOCOMP-130 recovery evidence without trusting arbitrary human comment text; invalidate evidence on branch/head drift; preserve fail-closed behavior for missing patches, partial ranges, ambiguous mappings, wrong epics, untrusted comments, and untested conflict resolution. Relevant code: direct epic maintenance completion/submission, integration metadata reconciliation, _reported_commit_landed_on_refs, _trusted_completion_evidence_landed, _child_has_durable_landing_evidence, epic review readiness/auto-close, tracker metadata schema, and lifecycle health. Required tests: exact EXOCOMP-148 two-commit range mapped to conflict-resolved 61141cb8/9663f4b2 with differing patch IDs; clean patch-equivalent rebase; partial or wrong mapping; stale target; deleted private ref; restart/backfill idempotency; forged human comment rejection; subsequent epic review creation and target-relative merge. Acceptance criteria: authorized, completely validated conflict-resolved rebases leave durable evidence that naturally unblocks the affected child and epic; EXOCOMP-130 proceeds to its parent review without rewriting private history or bypassing audits; ambiguous content remains blocked with one actionable recovery owner; focused rebase, landing, integration, epic review, restart, and security tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 11:12
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 11:12
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
