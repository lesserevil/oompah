---
id: OOMPAH-1265
type: task
status: Open
priority: 1
title: Prove external-prerequisite lifecycle convergence and observability
parent: OOMPAH-1231
children: []
blocked_by:
- OOMPAH-1266
start_blocked_by: &id001
- OOMPAH-1263
- OOMPAH-1264
labels: []
assignee: null
created_at: '2026-08-14T02:40:21.846935Z'
updated_at: '2026-08-20T23:10:35.463467Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: oompah-1231-lifecycle-acceptance-v1
  request_fingerprint: 4f48f1f0e957c03ae28cb1f4f01e0f52c4c6c9020d902bc67d1cfb4f69389377
oompah.start_blocked_by: *id001
oompah.lifecycle_revision: 1
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d1a591bae50708aaf359f111881a4071d274e23ddea4e3a15cbe53430d1b5800
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-20T23:10:27.550292+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Duplicate preflight verdict: no_duplicate\nMatches: none\n\
    # Duplicate Investigation for OOMPAH-1265\n\nI will analyze the supplied task\
    \ corpus to determine whether OOMPAH-1265 duplicates an existing active task.\n\
    \n## Task Decomposition Context\n\nThe corpus clearly shows OOMPAH-1231 (epic\
    \ parent, Open) deliberately decomposed the external-prerequisite work into four\
    \ sequential child tasks:\n\n1. **OOMPAH-1262** (Done) \u2014 Define typed authority\
    \ and profile capabilities\n2. **OOMPAH-1263** (Done) \u2014 Park blockers and\
    \ retire stale lanes  \n3. **OOMPAH-1264** (Done) \u2014 Resolve with exact CAS\
    \ and one generation\n4. **OOMPAH-1265** (Open) \u2014 Production acceptance and\
    \ observability \u2190 Current task\n5. **OOMPAH-1266** (Open, separate dependency)\
    \ \u2014 Fence late submission\n\n## OOMPAH-1265 Scope Analysis\n\n**OOMPAH-1265\
    \ is explicitly about:**\n- Production-shaped cross-component acceptance testing\n\
    - Lifecycle observability (dashboard/alerts, liveness, operator evidence)\n- Exercise\
    \ of concrete failure scenarios (TRICKLE-123/132/139/143)\n- Recovery documentation\
    \ and mutation/restart/race fencing\n- Tests: focused suites, deterministic restart/race,\
    \ terminal mutation scan\n\n**Evidence of distinct work:**\n- Prior comments document\
    \ local checkpoint at ea243c8f6 with two commits (clean)\n- 326 prerequisite/handoff/adapter\
    \ tests passing\n- 39 dashboard/detail tests passing  \n- 353 focused tests after\
    \ independent review (no blockers)\n- Concrete operator recovery guide at docs/external-prerequisites.md\n\
    - Signed off independent review at d30f77126271de8e22e8aff43a8653d6d8671afa\n\
    - Branch explicitly marked as finish-ordered after OOMPAH-1266, not pushed/submitted\n\
    \n## Candidate Exclusion\n\n**Terminal tasks (excluded):** OOMPAH-1262, 1263,\
    \ 1264 (Done); OOMPAH-1000\u20131075 (Merged/Done/Archived) \u2014 completed implementation\
    \ work, not acceptance targets.\n\n**Active non-duplicate tasks:**\n- **OOMPAH-1231**\
    \ (parent epic) \u2014 higher-level problem statement, not the acceptance layer\n\
    - **OOMPAH-1266** (open dependency) \u2014 completely different scope (submission/integration\
    \ authority fenci"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 189f40f2-e934-4bf7-981f-32d6a2044edb
oompah.work_contributors:
  runs:
  - run_id: 918690a581e24daa87b995a33ce25885--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1265
    source_sha: 02bd5960434a5c65dce259894737a55ab7a8ea96
    completed_at: '2026-08-20T23:10:27.554008+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2011
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2011
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2011
    cost_usd: 0.0
    recorded_at: '2026-08-20T23:10:27.549405+00:00'
---
## Summary

Add production-shaped cross-component acceptance for the complete external-prerequisite lifecycle: trusted worker handoff, exact parking, zero-job authority publication, restart convergence, named dependency/operator observability, prerequisite resolution, and exactly one continuation generation. Exercise TRICKLE-123 repeated unavailable-platform handoffs, TRICKLE-132 cross-project dependency/head drift, TRICKLE-139 auxiliary repair retirement, and TRICKLE-143 structured review continuation. Verify dashboard and alerts distinguish situation-normal dependency waits from named operator action, liveness has no unexplained divergence, and old jobs cannot mutate after resolution. Update user-facing operator documentation only where a concrete resolution action exists. Required checks: focused workflow/runtime/liveness/server/UI suites, deterministic restart/race tests, terminal mutation scan, and complete Makefile gate. Acceptance: live-shaped tasks remain quiet while blocked, survive restart, resume once when truthfully resolved, and expose precise recovery evidence without generic warning floods.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 06:03
---
Added finish-order dependency on OOMPAH-1266 (not hard-start): lifecycle acceptance/test-only work may begin after existing OOMPAH-1264 hard-start clears, but final OOMPAH-1265 integration follows the landed late-submit authority repair because both touch server/continuation observability boundaries.
---
author: oompah
created: 2026-08-14 07:34
---
Claimed for direct implementation in /home/shedwards/src/oompah-1265 on branch OOMPAH-1265 from landed OOMPAH-1264 epic head 2ff3966dd. Oompah remains paused. Beginning production-shaped test-first lifecycle acceptance in parallel while OOMPAH-1266 completes its bounded integration-authority gate; final integration remains finish-ordered after OOMPAH-1266.
---
author: oompah
created: 2026-08-14 07:55
---
Test-first lifecycle checkpoint frozen locally at ea243c8f6 (two commits, clean). Production-shaped TRICKLE-123/132/139/143 acceptance exposed and fixed replacement-after-receipt transition fencing plus truthful 409 handoff-authority conflicts. Combined prerequisite/handoff/adapter suite passes 326 tests. Task detail now exposes exact non-secret resolution CAS fields outside the global alert surface; dashboard/detail tests pass 39 tests; concrete project-owner recovery is documented in docs/external-prerequisites.md. Final integration remains finish-ordered after OOMPAH-1266 and is not pushed/submitted.
---
author: oompah
created: 2026-08-14 08:28
---
Independent bounded review signed off exact clean head d30f77126271de8e22e8aff43a8653d6d8671afa. Post-cut prerequisite ABA fencing is enforced inside the status-write lane; structured handoffs invalidate the authoritative issue snapshot and project/projectless detail caches then refresh+broadcast on accepted and durable-conflict paths; cross-scope records are malformed/non-resolvable and UI suppresses the CLI affordance. Reviewer reran 353 focused tests with no blockers. Branch remains local/unsubmitted pending finish-order integration after OOMPAH-1266.
---
author: oompah
created: 2026-08-20 23:09
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:10
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 49s
- Log: OOMPAH-1265__20260820T230953Z.jsonl
---
<!-- COMMENTS:END -->
