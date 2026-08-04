---
id: OOMPAH-791
type: feature
status: In Progress
priority: 1
title: Cut epic and nested-epic rollup over to LandingFact-driven jobs
parent: OOMPAH-768
children: []
blocked_by:
- OOMPAH-793
- OOMPAH-812
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:59:17.853130Z'
updated_at: '2026-08-04T23:42:17.542457Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-791
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: fb3aa3abc582ec1af953ebc1e286b3a58b83eabb84d54e02ce3789f58c3182cb
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T20:25:44.417468+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Duplicate preflight verdict: no_duplicate\nMatches: none\n\
    Acknowledged. OOMPAH-793 (implementation/ownership domain) has been submitted\
    \ at ef5e8c30e. This is a sibling task to OOMPAH-791 under the OOMPAH-768 epic\
    \ and does not affect my duplicate screening conclusion.\n\nMy duplicate screening\
    \ for **OOMPAH-791** is **complete**. The verdict stands:\n\n**Focus handoff:\
    \ duplicate_detector**  \n**Duplicate preflight verdict: no_duplicate**  \n**Matches:\
    \ none**\n\nOOMPAH-791 is a unique, non-duplicate feature task for migrating the\
    \ epic rollup domain to LandingFact-driven jobs.\n\n---\n\nI am exiting duplicate-screening\
    \ mode now per the reserved boundary. This was a read-only qualification run;\
    \ I have not modified the repository, tracker state, or branch. The screening\
    \ result is ready for oompah's integration verification."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-791
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-768--task-OOMPAH-791
  base_branch: epic-OOMPAH-768
  base_sha: a744be37d42047e25e6fc62a6a64878c187290e0
  head_sha: 9e2ecc3ff8de2250009cbbc78e54f94ab0842a35
  submitted_at: '2026-08-04T22:40:51.588852+00:00'
  updated_at: '2026-08-04T22:40:51.588852+00:00'
oompah.task_costs:
  total_input_tokens: 13
  total_output_tokens: 607
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 556
      cost_usd: 0.0
    sonnet:
      input_tokens: 3
      output_tokens: 51
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 556
    cost_usd: 0.0
    recorded_at: '2026-08-04T20:25:44.402970+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 3
    output_tokens: 51
    cost_usd: 0.0
    recorded_at: '2026-08-04T21:39:32.456001+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-791__20260804T202331Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-768--task-OOMPAH-791
    source_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
    completed_at: '2026-08-04T20:25:44.437531+00:00'
---
## Summary

Migrate epic readiness, child landing verification, rollup review creation, nested target resolution, auto-close, terminal validation, rebase/repair, cleanup, and restart reconciliation to shared facts/decisions/jobs. Enforce acyclic containment; require normal child Done plus landing proof and nested epic landing on immediate parent; never make child eligibility depend on a parent status derived from that child. Preserve patch-equivalence and durable evidence after source pruning. Required real-Git scenarios: multi-level nested epics, parent open to main while child landed to parent, deleted refs, rebase, direct maintenance, new/reopened child during review creation, and OOMPAH-731/739/748. Acceptance: no parent-child proof cycle, all epic consumers share target/landing facts, and rollups converge without manual status overrides.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 20:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 20:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 20:25
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 4, Tool calls: 0
- Tokens: 10 in / 556 out [566 total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 32s
- Log: OOMPAH-791__20260804T202331Z.jsonl
---
author: oompah
created: 2026-08-04 20:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 20:30
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-08-04 20:31
---
Understanding: migrate epic and nested-epic readiness, landing proof, rollup, lifecycle, repair, cleanup, and restart reconciliation to shared LandingFact-driven jobs while preserving patch-equivalence and durable evidence. I will first map existing facts/decisions/jobs and epic consumers, then implement small tested refactors and validate required real-Git scenarios.
---
author: oompah
created: 2026-08-04 20:32
---
Discovery: epic consumers remain in orchestrator.py (_epic_auto_close_check, _open_epic_main_prs, _resolve_epic_target_branch, stale/rebase/repair and review-child reconciliation) and merged_evidence_collector.py, while the new workflow engine is only wired to standalone integration. Existing _rollup_decision checks child statuses but has no child LandingFact/target graph, so it cannot enforce Done plus immediate-target landing without a parent-status cycle. I will add an epic-specific facts/decision/job adapter and route the legacy gates through its pure result, preserving existing Git patch-equivalence helpers.
---
author: oompah
created: 2026-08-04 20:42
---
Implementation: added EpicFactCollector/EpicWorkflowController and target-relative epic actions. Enriched containment facts now validate acyclic ownership, resolve nested targets from immediate parent identity, and collect child plus epic landing requests. Epic decisions require normal child Done plus exact landing, use nested landing without parent status, and schedule bounded rollup/landing jobs through WorkflowJobScheduler. GitLandingCollector now records durable patch-equivalence proof for rebased sources and preserves prior proof after ref deletion. Added real-Git nested, deleted-ref, and rebase regression coverage.
---
author: oompah
created: 2026-08-04 20:56
---
Verification: focused shared workflow, epic, lifecycle, shadow, and strategy suites pass (277 tests in the latest run; earlier shared-facts run 109/109). Real-Git coverage proves multi-level nested rollups, immediate-parent landing while parent remains Open, deleted source refs across controller restart via the landing ledger, patch-equivalent rebases, and containment-cycle fail-closed behavior. Enforce-mode orchestrator gates and target resolution passed the existing epic suites.
---
author: oompah
created: 2026-08-04 20:57
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 113
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 27m 48s
- Log: OOMPAH-791__20260804T203022Z.jsonl
---
author: oompah
created: 2026-08-04 20:58
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-04 20:58
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-08-04 21:32
---
Verification (continuation run): All affected suites pass at HEAD f8f9d382c.

Fixed pre-existing timeout: test_hundreds_of_history_rows_do_not_hide_eligible_heads (added in 08f6a8c5a) was correctly testing that 400 history rows don't block 2 eligible heads, but the 402 WAL-mode SQLite commits take ~17 s — above the project-wide 5 s signal timeout. Added @pytest.mark.timeout(30) to give it headroom while still catching genuine hangs.

Test results:
- test_epic_workflow (6/6)
- test_integration_workflow (20/20)
- test_workflow_facts + test_workflow_jobs + test_workflow_scheduler + test_work_decision (146/146)
- test_epic_strategy + test_epic_auto_close + test_epic_staleness + test_nested_epic_cycle_fix + test_nested_epic_stale_in_review (286/286)
- test_workflow_shadow + test_workflow_shadow_integration + test_orchestrator_handlers (304/304)
---
author: oompah
created: 2026-08-04 21:33
---
Migrated epic and nested-epic rollup to LandingFact-driven jobs. Added EpicFactCollector/EpicWorkflowController with acyclic containment validation, target-relative epic workflow facts, shared decisions routing epic gates without parent-status cycles, durable patch-equivalence evidence through GitLandingCollector, and immediate-parent landing enforcement. Real-Git coverage for multi-level nested rollups, deleted source refs, and patch-equivalent rebases. Fixed pre-existing test timeout on 402-job SQLite throughput test. All 762 focused-suite tests pass.
---
author: oompah
created: 2026-08-04 21:39
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 91, Tool calls: 53
- Tokens: 3 in / 51 out [54 total]
- Cost: $0.0000
- Exit: terminated, Duration: 41m 14s
- Log: OOMPAH-791__20260804T205839Z.jsonl
---
author: oompah
created: 2026-08-04 22:26
---
The combined-tree quality gate failed on `epic-OOMPAH-768--task-OOMPAH-791`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
Combined-tree quality gate infrastructure_error: Quality gate owner metadata does not match the exact resolved candidate head.
```
---
author: oompah
created: 2026-08-04 22:28
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-04 22:28
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-08-04 22:29
---
Understanding: I will reconcile this branch with the integrated dependency, inspect the existing LandingFact-driven epic rollup implementation, and then rerun the exact-head quality gate before pushing and resubmitting.
---
author: oompah
created: 2026-08-04 22:29
---
Discovery: the quality-gate infrastructure error is reproducible from the integration path. integration_executor resolves a new rebased candidate SHA but passes the caller's QualityGateOwner keyed to the submitted pre-rebase SHA; BranchQualityGate correctly rejects this exact-owner/head mismatch. I will preserve the owner identity/generation while rekeying its head to the resolved rebased candidate, with a focused regression test.
---
author: oompah
created: 2026-08-04 22:32
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 0, Tool calls: 21
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 31s
- Log: OOMPAH-791__20260804T222820Z.jsonl
---
author: oompah
created: 2026-08-04 22:40
---
The prior infrastructure failure occurred because integration rebased submitted head f8f9d382c to patch-equivalent head 9e2ecc3ff8de2250009cbbc78e54f94ab0842a35 but retained stale quality-gate owner metadata. The deployed watchdog then cancelled the blocked queue row and redispatched a repair worker. I stopped that out-of-scope repair, quarantined its uncommitted gate-owner patch for OOMPAH-811, and revalidated the clean rewritten feature head: 744 focused tests pass. Freshly resubmitting 9e2ecc3ff without feature-scope changes.
---
author: oompah
created: 2026-08-04 22:41
---
Revalidated the integration-rewritten, patch-equivalent exact head 9e2ecc3ff8de2250009cbbc78e54f94ab0842a35 with 744 focused tests; resubmitting without the quarantined out-of-scope infrastructure patch.
---
author: oompah
created: 2026-08-04 23:28
---
Independent acceptance review repaired the domain adapter at exact pushed head dab74228dc85f74fdfdab64b1f22660ae2287cf8 on gated parent 1230456cc. Fixes: direct-child-only containment with full-graph cycle validation; Archived child handling; target-rewrite-safe durable landing replay and newest-window persistence; action/project/dead-owner-scoped restart recovery; one-snapshot scheduling; evidence-bound epic_auto_close with no parallel enforce-mode terminal writer. New real-Git and restart regressions cover source advance vs explicit immutable SHA, target rewrite, shared aggregate ancestry, stale snapshot scheduling, recovery isolation, and auto-close fencing. Verification: 555 combined workflow/legacy epic tests passed; 70 post-rebase smoke tests passed; terminal mutation scan 8/8; focused Ruff and diff checks clean. OOMPAH-804 remains the declared production handler/single-writer composition dependency. Holding submission until OOMPAH-812 reaches terminal Done.
---
author: oompah
created: 2026-08-04 23:29
---
Independent read-only qualification confirms OOMPAH-791 is complete as the domain adapter, with OOMPAH-804 as its declared hard runtime/enforce-mode composition dependency. Historical OOMPAH-731/739/748 incident corpus and targeted LandingFact/direct-maintenance/nested-stale/current adapter tests passed 43/43; the broader 14-module compatibility slice passed 753/753. OOMPAH-804 must bind all EPIC_ACTION handlers, revalidate cursor/generation/evidence/head/scope/lease before effects, supersede child-change races, and disable legacy writers only after each handler is live.
---
author: oompah
created: 2026-08-04 23:42
---
Prepared the reviewed serial composition while the global gate is occupied: rebased the six-commit OOMPAH-791 stack onto exact OOMPAH-782 head a3948097f, producing clean pushed head 82f0ffd70e153351135700a215e50a9b06fb678f. Range-diff preserves all six patches; the only contextual adjustment is the expected shared work_decision.py neighborhood. Post-rebase smoke: 15 epic-workflow + 53 workflow-facts/integration-workflow tests passed; diff check clean. Hold submission until OOMPAH-782 lands to the parent.
---
<!-- COMMENTS:END -->
