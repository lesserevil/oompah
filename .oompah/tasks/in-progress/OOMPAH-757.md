---
id: OOMPAH-757
type: bug
status: In Progress
priority: 1
title: Persist canonical child landing evidence through conflict-resolved epic rebases
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- focus-complete:docs
assignee: null
created_at: '2026-08-04T11:11:32.097478Z'
updated_at: '2026-08-04T11:26:01.263049Z'
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
  verdict: no_duplicate
  checked_at: '2026-08-04T11:13:08.530823+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active peer task matches this issue. Closest related\
    \ tasks\u2014OOMPAH-162, OOMPAH-165, and OOMPAH-168\u2014are terminal Archived\
    \ tasks addressing different epic-landing behavior.\nFocus handoff: duplicate_detector\
    \  \nDuplicate preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence:\
    \ No active peer task matches this issue. Closest related tasks\u2014OOMPAH-162,\
    \ OOMPAH-165, and OOMPAH-168\u2014are terminal Archived tasks addressing different\
    \ epic-landing behavior."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 2a6369a3-3dec-483c-b5ae-5d825c54cd6c
oompah.task_costs:
  total_input_tokens: 47331
  total_output_tokens: 265
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 47331
      output_tokens: 265
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 47149
    output_tokens: 216
    cost_usd: 0.0
    recorded_at: '2026-08-04T11:13:08.529965+00:00'
  - profile: default
    model: haiku
    input_tokens: 182
    output_tokens: 49
    cost_usd: 0.0
    recorded_at: '2026-08-04T11:19:38.531148+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-757__20260804T111243Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-757
    source_sha: 5368e23617a98569caf7370b0f2eb63d41c8ba6b
    completed_at: '2026-08-04T11:13:08.554499+00:00'
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
author: oompah
created: 2026-08-04 11:13
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 47.1K in / 216 out [47.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 39s
- Log: OOMPAH-757__20260804T111243Z.jsonl
---
author: oompah
created: 2026-08-04 11:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 11:14
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-04 11:17
---
Understanding: OOMPAH-757 requires implementing a new feature to persist canonical child landing evidence through conflict-resolved epic rebases. The task involves:

1. Tracker metadata schema changes to store landing evidence (old base/head/range, new canonical range/head, target epic branch, rebase helper/task, pre/post refs, validation result, fingerprint)
2. Implementation of evidence persistence and consumption in functions like _child_landing_evidence_block_reason, _trusted_completion_evidence_landed, _child_has_durable_landing_evidence
3. Epic review readiness/auto-close logic updates
4. Comprehensive test coverage including conflict-resolved rebase mappings, patch equivalence, partial/wrong mappings, stale targets, and security tests

This is a backend/implementation-focused task requiring code changes, schema modifications, and integration testing. As a Technical Writer focused on documentation only, this is outside my scope. The appropriate next focus should be a backend/feature specialist who can implement the required code changes and write the corresponding tests.
---
author: oompah
created: 2026-08-04 11:19
---
HANDOFF: This task requires backend/feature implementation work, not documentation. As a Technical Writer, I'm handing off to a Feature Developer or backend specialist. 

Key context for next agent:
- Issue addresses regression in OOMPAH-747 where conflict-resolved rebases don't persist landing evidence
- Live case: EXOCOMP-130 blocked because commits 4e013110 (one of two in EXOCOMP-148) aren't recognized as landed despite being rebased into canonical epic commits 61141cb8/9663f4b2 with conflict resolution
- Current system only accepts exact ancestry/patch equivalence or Oompah-authored completion SHAs; no conflict-resolved rebase mapping support
- Implementation scope includes schema changes, evidence persistence/consumption functions, epic review readiness updates, and comprehensive test coverage (especially conflict-resolved mappings with differing patch IDs)
- Recommended next focus: feature
---
author: oompah
created: 2026-08-04 11:19
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 10
- Tokens: 182 in / 49 out [231 total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 59s
- Log: OOMPAH-757__20260804T111450Z.jsonl
---
author: oompah
created: 2026-08-04 11:23
---
Operator recovery for OOMPAH-759: the documentation focus completed a valid handoff, but its scheduled deep-profile retry self-aborted after writing In Progress, leaving this task without a worker. Returning only this task to Open now; duplicate screening is already current and the needs:feature label should route the next fresh dispatch to implementation. No branch or implementation evidence is being changed.
---
author: oompah
created: 2026-08-04 11:24
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-04 11:24
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-04 11:25
---
Understanding: This is a backend bug, not a documentation gap. The fix must add durable, service-authored canonical landing mappings for authorized conflict-resolved epic rebases, validate freshness/completeness/epic identity, and preserve fail-closed review readiness. In the assigned docs focus I will locate the concrete implementation and test surfaces, confirm whether any documentation change is warranted, then leave a Focus handoff: docs comment and route to needs:feature without changing behavior.
---
<!-- COMMENTS:END -->
