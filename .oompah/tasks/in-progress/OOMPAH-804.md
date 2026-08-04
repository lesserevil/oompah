---
id: OOMPAH-804
type: task
status: In Progress
priority: 1
title: Wire durable workflow domains into the production runtime
parent: OOMPAH-768
children: []
blocked_by:
- OOMPAH-781
- OOMPAH-782
- OOMPAH-791
- OOMPAH-793
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T19:34:18.669662Z'
updated_at: '2026-08-04T20:33:53.291368Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-804
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 26f73b31db54d6fda10efb4c22f0e4338ae50da00232ad0c90e371520a79893b
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T20:26:03.976000+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed required peers OOMPAH-768 (parent epic), OOMPAH-781/782/791/793\
    \ (domain-specific dependencies, all Open or Ready to Integrate), and OOMPAH-788\
    \ (Done, prior integration domain). OOMPAH-804 is the final runtime-level integration\
    \ task that composes all domain adapters into production infrastructure. No active\
    \ task describes the same top-level wiring, lifecycle management, and multi-domain\
    \ coordination work. The four blocked-by dependencies confirm OOMPAH-804 is the\
    \ orchestration layer, not a domain task.\nLooking at the supplied task corpus,\
    \ I need to investigate whether OOMPAH-804 duplicates any active issue.\n\n##\
    \ Analysis\n\n**OOMPAH-804** is described as: \"Implement the **final production-runtime\
    \ integration** for OOMPAH-768 **after the domain adapters exist**. Construct\
    \ and lifecycle-manage the shared WorkflowFact collectors, domain controllers,\
    \ WorkflowJobStore, DurableWorkflowWorker, and TaskTransitionService bindings\
    \ from service startup.\"\n\nThe task explicitly depends on four sibling domain-specific\
    \ features:\n- **OOMPAH-781** (Open): \"Cut terminal-audit lifecycle over to durable\
    \ decisions and jobs\" \u2014 specific to audit domain\n- **OOMPAH-782** (Open):\
    \ \"Cut review and CI reconciliation over to durable decisions and jobs\" \u2014\
    \ specific to review/CI domain\n- **OOMPAH-791** (Open): \"Cut epic and nested-epic\
    \ rollup over to LandingFact-driven jobs\" \u2014 specific to epic rollup domain\n\
    - **OOMPAH-793** (Ready to Integrate): \"Cut implementation, direct-owner, handoff,\
    \ and retry ownership over to durable jobs\" \u2014 specific to implementation\
    \ domain\n\nAnd OOMPAH-788 (Done): Individual integration-domain cutover (already\
    \ completed).\n\n**OOMPAH-804** is architecturally distinct from these:\n- The\
    \ domain tasks each migrate **one workflow domain** to durable decisions\n- OOMPAH-804\
    \ is the **top-level runtime integration** that:\n  1. Depends on all domain work\
    \ being available\n  2. Constructs shared infrastructure (WorkflowFact collectors,\
    \ domain controllers, TaskTransitionService)\n  3. Routes events from **multiple\
    \ domains** through durable controllers\n  4. Manages worker lifecycle and restart\
    \ recovery across all domains\n  5. Drives UI projections from the unified durable\
    \ decisions\n\nThe description explicitly states it comes \"**after** the domain\
    \ adapters exist,\" confirming this is composition/integration work, not domain-specific\
    \ implementation.\n\nNo other task in the corpus describes this final production-runtime\
    \ wiring layer.\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight\
    \ verdi"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8edc58c4-bdea-4958-9ab7-7ef87e923988
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-804
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-768--task-OOMPAH-804
  base_branch: epic-OOMPAH-768
  base_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
  updated_at: '2026-08-04T20:23:56.568541+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2234
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2234
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2234
    cost_usd: 0.0
    recorded_at: '2026-08-04T20:26:03.969511+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-804__20260804T202423Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-768--task-OOMPAH-804
    source_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
    completed_at: '2026-08-04T20:26:04.014658+00:00'
---
## Summary

Implement the final production-runtime integration for OOMPAH-768 after the domain adapters exist. Construct and lifecycle-manage the shared WorkflowFact collectors, domain controllers, WorkflowJobStore, DurableWorkflowWorker, and TaskTransitionService bindings from service startup. Route production dispatch and implementation/direct-owner claims, releases, duplicate screening, focus handoff, validation submission, worker exit, authority revocation, retries, integration delivery, terminal audit, review/CI, and epic rollup events through the durable controllers; recover and drain workers safely across restart; drive UI ownership, waiting, retry, and reason projections from the same durable decisions. Add per-domain shadow comparison before enforce cutover and disable the corresponding legacy writers/reconcilers in enforce mode without deleting rollback code (OOMPAH-794 owns final deletion). Relevant context includes oompah/orchestrator.py, server/app startup and shutdown, oompah/workflow_*.py, domain workflow modules, API/WebSocket projections, .env.example, and existing transition-service wiring. Required tests: production-like native tracker plus temporary Git/forge doubles, startup migration, crash/restart with leased and retry-wait jobs, event-order races, drain/restart, shadow parity, enforce-mode single-writer assertions, and UI/executor reason parity; run make test. Acceptance: every migrated domain is constructed and active in production, each lifecycle event has one durable owner, restart resumes rather than duplicates work, UI state derives from the same accepted decision, and enforce mode has no active legacy lifecycle writer.

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
created: 2026-08-04 20:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 20:26
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.2K out [2.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 14s
- Log: OOMPAH-804__20260804T202423Z.jsonl
---
<!-- COMMENTS:END -->
