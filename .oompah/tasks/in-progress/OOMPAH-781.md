---
id: OOMPAH-781
type: feature
status: In Progress
priority: 1
title: Cut terminal-audit lifecycle over to durable decisions and jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:58:59.010872Z'
updated_at: '2026-08-04T20:38:12.149812Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-781
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3e730440ffde04145aa9c18b89db7431eda9a2cd7a481c12d5b3ab63ea7ce0e7
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T20:24:23.241257+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-781 describes a unique domain cutover task within\
    \ the OOMPAH-768 epic (\"Migrate every workflow domain to shared decisions and\
    \ durable jobs\"). The terminal-audit lifecycle domain is distinct from the active\
    \ sibling domain tasks: OOMPAH-782 (review/CI domain), OOMPAH-791 (epic rollup\
    \ domain), and OOMPAH-793 (implementation/direct-owner domain). While OOMPAH-768\
    \ is the parent epic covering multiple domains, OOMPAH-781 is specifically scoped\
    \ to audit request ownership, candidate selection, launch, rotation, finalization,\
    \ result application, retries, and exhaustion. No existing active task covers\
    \ this specific terminal-audit domain cutover. All similar-scored archived tasks\
    \ (OOMPAH-158\u2013OOMPAH-303, OOMPAH-398) are in terminal states and therefore\
    \ excluded as duplicate candidates per the rules. OOMPAH-804 is a production-integration\
    \ wrapper task, not a duplicate implementation.\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-781\
    \ describes a unique domain cutover task within the OOMPAH-768 epic (\"Migrate\
    \ every workflow domain to shared decisions and durable jobs\"). The terminal-audit\
    \ lifecycle domain is distinct from the active sibling domain tasks: OOMPAH-782\
    \ (review/CI domain), OOMPAH-791 (epic rollup domain), and OOMPAH-793 (implementation/direct-owner\
    \ domain). While OOMPAH-768 is the parent epic covering multiple domains, OOMPAH-781\
    \ is specifically scoped to audit request ownership, candidate selection, launch,\
    \ rotation, finalization, result application, retries, and exhaustion. No existing\
    \ active task covers this specific terminal-audit domain cutover. All similar-scored\
    \ archived tasks (OOMPAH-158\u2013OOMPAH-303, OOMPAH-398) are in terminal states\
    \ and therefore excluded as duplicate candidates per the rules. OOMPAH-804 is\
    \ a production-integration wrapper task, not a duplicate implementation."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 85e821e6-3fe4-41e2-a4c3-34d2d51ca7b3
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-781
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-768--task-OOMPAH-781
  base_branch: epic-OOMPAH-768
  base_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
  updated_at: '2026-08-04T20:26:42.094071+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1252
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1252
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1252
    cost_usd: 0.0
    recorded_at: '2026-08-04T20:24:23.239960+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-781__20260804T202239Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-768--task-OOMPAH-781
    source_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
    completed_at: '2026-08-04T20:24:23.267882+00:00'
---
## Summary

Migrate audit request ownership, candidate selection, launch, rotation, finalization, result application, retries, exhaustion, and historical recovery into durable workflow jobs while retaining TerminalTransitionCoordinator safety. Model queued/running/finalizing/retry-wait/action-required explicitly; ensure normal candidate rotation/transport retry is informational; guarantee result finalization cannot be starved by comments/output; preserve independent-candidate policy and exact evidence. Required tests: no candidate, transport failure, dynamic policy denial, duplicate/revoked auditor, oversized output, restart at each stage, deleted branches, finalization starvation, and current audit enforcement suites. Acceptance: every In Validation task has a durable audit disposition and bounded recovery; no valid verdict is lost or indefinitely pending.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 20:22
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 20:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 20:24
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 5s
- Log: OOMPAH-781__20260804T202239Z.jsonl
---
author: oompah
created: 2026-08-04 20:26
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 20:26
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-04 20:27
---
Understanding: migrate terminal-audit ownership, candidate/launch/rotation/finalization/result/retry/recovery into durable decisions and jobs, preserving TerminalTransitionCoordinator safety and independent-candidate/evidence guarantees. I will first map existing lifecycle and persistence patterns, then implement focused changes with restart/starvation/auth/retry coverage.
---
author: oompah
created: 2026-08-04 20:27
---
Discovery: durable workflow_jobs/workflow_scheduler/workflow_worker infrastructure is present, while terminal-audit enforcement still owns a periodic monolithic scan and direct auditor launch. The cutover seam is the orchestrator enforcement/dispatch path; durable audit jobs will own phase/recovery and TerminalTransitionCoordinator will remain the sole result/status applicator.
---
author: oompah
created: 2026-08-04 20:38
---
Implementation: added terminal_audit_workflow durable adapter over WorkflowJobStore, phase-aware failure/recovery and phase telemetry in the ledger, wired enforcement/dispatch/retry/finalization into Orchestrator, and carried only non-secret workflow job identity on RunningEntry. Finalization is checkpointed before coordinator side effects; output/comments are excluded from checkpoints. Focused suites: 176 passed.
---
<!-- COMMENTS:END -->
