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
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:59:17.853130Z'
updated_at: '2026-08-04T22:28:04.947933Z'
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
oompah.agent_run_id: d501a887-3a5d-433d-b5a6-fbc241e45e9b
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-791
oompah.integration:
  version: 2
  state: blocked
  attempts: 1
  task_branch: epic-OOMPAH-768--task-OOMPAH-791
  base_branch: epic-OOMPAH-768
  base_sha: a744be37d42047e25e6fc62a6a64878c187290e0
  head_sha: 9e2ecc3ff8de2250009cbbc78e54f94ab0842a35
  submitted_at: '2026-08-04T21:32:56.564220+00:00'
  updated_at: '2026-08-04T22:26:39.129519+00:00'
  last_error: 'Combined-tree quality gate infrastructure_error: Quality gate owner
    metadata does not match the exact resolved candidate head.'
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
<!-- COMMENTS:END -->
