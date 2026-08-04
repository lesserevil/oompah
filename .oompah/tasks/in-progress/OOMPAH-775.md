---
id: OOMPAH-775
type: task
status: In Progress
priority: 1
title: Route API and auxiliary status writes through TaskTransitionService and enforce
  the boundary
parent: OOMPAH-769
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-776
labels: []
assignee: null
created_at: '2026-08-04T13:58:48.205609Z'
updated_at: '2026-08-04T21:30:26.732924Z'
work_branch: epic-OOMPAH-769--task-OOMPAH-775
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e4b3c9e4e57affbaade0b5587360810bc864502d6a3197b59d93a3869052f197
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T21:26:46.931306+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: ** OOMPAH-775 is the canonical task for routing API/CLI/watchdog/audit/auxiliary
    writers through TaskTransitionService. OOMPAH-803 is the duplicate of OOMPAH-775
    (as confirmed by OOMPAH-775''s own comment), now in parallel implementation despite
    pending archival. Coordination via epic-sibling advisory is available.

    Thank you for that coordination message. This is important context.


    The coordination confirms that OOMPAH-803 has just started implementation. However,
    this **reinforces** rather than changes my duplicate assessment:


    **Analysis of Coordination Impact:**


    - **OOMPAH-775**: Marked as the "canonical task" (per OOMPAH-775''s own comment
    "Promoting the canonical task")

    - **OOMPAH-803**: Marked as "the later duplicate" in the same comment, queued
    for archival

    - **Current Status**: OOMPAH-803 just started implementation despite being queued
    for terminal transition to Archived


    **Duplicate Investigation Result Unchanged:**


    OOMPAH-775 is **not a duplicate**. It is the canonical task. OOMPAH-803 is the
    duplicate (though it hasn''t been archived yet).


    **Coordination Concern for Next Agent:**


    However, there is an **active coordination issue**: OOMPAH-803 (epic-sibling)
    has started implementation on identical scope (API/CLI/watchdog/audit/auxiliary
    routing) while queued for archival. This risks:

    - Duplicate implementation effort

    - Conflicting changes to the same files

    - Integration conflicts when both branches are completed


    The next agent working on OOMPAH-775 should:

    1. Monitor OOMPAH-803''s progress via `oompah coordinate`

    2. Consider fast-tracking to prevent divergent implementations

    3. Be prepared for merge coordination if both proceed in parallel


    ---


    **Focus handoff: duplicate_detector**


    **Duplicate preflight verdict: no_duplicate**


    **Matches: none**


    **Evidence:** OOMPAH-775 is the canonical task for routing API/CLI/watchdog/audit/auxiliary
    writers through TaskTransitionService. OOMPAH-803 is the duplicate of OOMPAH-775
    (as confirmed by OOMPAH-775''s own comment), now in parallel implementation despite
    pending archival. Coordination via epic-sibling advisory is available.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 0ca57b14-41af-4f26-b451-f10500389e57
oompah.work_branch: epic-OOMPAH-769--task-OOMPAH-775
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-769--task-OOMPAH-775
  base_branch: epic-OOMPAH-769
  base_sha: 6561d52e5a879375ea3587582f335419ed49310e
  updated_at: '2026-08-04T21:24:14.385412+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1457
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1457
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1457
    cost_usd: 0.0
    recorded_at: '2026-08-04T21:26:46.920026+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-775__20260804T212425Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-769--task-OOMPAH-775
    source_sha: 6561d52e5a879375ea3587582f335419ed49310e
    completed_at: '2026-08-04T21:26:46.948603+00:00'
---
## Summary

Migrate server API/CLI handoff paths, stalled_task_watchdog, terminal_audit_enforcement, ACP tools, intake bridges, project maintenance, and remaining production modules to TaskTransitionService. Retain tracker adapter implementations but forbid direct production status calls with an AST/static architectural test and terminal-audit scan integration. Preserve authenticated principal/owner rules and response compatibility. Required tests: REST/CLI transitions, actor mismatch, owner claim, intake promotion, Needs Human instructions, terminal aliases, auxiliary recovery, and architectural boundary violations. Acceptance: only TaskTransitionService and tracker adapters may write status; every transition is journaled and reason-coded.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:22
---
Prerequisite OOMPAH-776 is Done and the later duplicate OOMPAH-803 has been archived. Promoting the canonical task so the server can dispatch the remaining OOMPAH-769 boundary work.
---
author: oompah
created: 2026-08-04 21:24
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 21:24
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 21:26
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 4, Tool calls: 0
- Tokens: 10 in / 1.5K out [1.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 43s
- Log: OOMPAH-775__20260804T212425Z.jsonl
---
author: oompah
created: 2026-08-04 21:30
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
