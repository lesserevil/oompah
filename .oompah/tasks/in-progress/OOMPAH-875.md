---
id: OOMPAH-875
type: task
status: In Progress
priority: null
title: Prevent slow scheduler lanes from starving Ready integration claims
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T08:44:33.807355Z'
updated_at: '2026-08-07T09:25:15.506708Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-875
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e89e104efd8da99c68e706e9e416c2db51b30f62fd17f04c8dab8f82c683df24
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T08:52:53.895812+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Examined all 11 required peer tasks under epic parent\
    \ OOMPAH-768. OOMPAH-788 (Done) completed integration workflow architecture migration\
    \ to durable jobs but does not address scheduler lane ordering/prioritization.\
    \ OOMPAH-875 is a post-cutover performance regression (2026-08-07) where slow\
    \ dispatch/audit lanes starve integration claims despite available validation\
    \ capacity. OOMPAH-874 (In Progress) addresses gate cancellation classification,\
    \ a separate concern. No active task duplicates this scheduler lane starvation\
    \ issue. Closest completed sibling (OOMPAH-788) is architectural groundwork, not\
    \ the specific tick-ordering fix needed for OOMPAH-875.\nLet me systematically\
    \ analyze the task corpus for potential duplicates:\n\n**OOMPAH-875 Problem Summary:**\n\
    - **Core Issue**: Scheduler performance regression (2026-08-07) where eligible\
    \ Ready integration claims are starved by slow lanes\n- **Root Cause**: `_process_integration_queues`\
    \ scheduled too late in the orchestrator tick (after reconcile, review, dispatch,\
    \ YOLO, watchdog)\n- **Specific Regression**: Integration claim delayed 8+ minutes\
    \ despite idle validation broker; first post-cutover tick took 366s (320s dispatch\
    \ + 175s terminal-audit)\n- **Solution Needed**: Prioritize integration work or\
    \ give it its own promptly-woken lane\n\n**Analysis of Peer Tasks:**\n\n1. **OOMPAH-768**\
    \ (In Progress - Epic Parent): Broader workflow domain migration to durable jobs.\
    \ Not specific to scheduler lane ordering.\n\n2. **OOMPAH-788** (Done): \"Cut\
    \ integration delivery over to shared decisions and durable jobs\"\n   - Architectural\
    \ refactoring to durable workflow jobs\n   - Completed BEFORE the 2026-08-07 regression\n\
    \   - Addresses eligibility/claiming/quality-gate, NOT scheduler lane prioritization\n\
    \   - Appears to be a prerequisite, not a duplicate\n\n3. **OOMPAH-874** (In Progress):\
    \ \"Classify cancelled exact gates as retryable scheduling\"\n   - Distinct problem:\
    \ gate cancellation classification\n   - Not about scheduler lane starvation\n\
    \n4. **OOMPAH-812** (Done): \"Drain synthetic long-tick ordering fixtures\"\n\
    \   - Test fixture cleanup (dispatch-before-maintenance assertion)\n   - Different\
    \ context (testing), not production scheduler ordering\n\n5. **OOMPAH-819**, **OOMPAH-813**,\
    \ other siblings: Address different concerns (review metadata, worker exits, etc.)\n\
    \n**Key Finding**: OOMPAH-875 addresses a **post-cutover performance regression**\
    \ discovered on 2026-08-07 \u2014 a scheduler tick ordering issue that wasn't\
    \ the focus of the earlier architecture migration (OOMPAH-788). No active task\
    \ in the corpus describes this specific scheduler lane starvation problem.\n\n\
    ---\n\nFocus handoff: duplicate_detector\n\nDupl"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: eb3c671b-557d-472d-b96f-f9101577659e
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-875
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-768--task-OOMPAH-875
  base_branch: epic-OOMPAH-768
  base_sha: 6a84d9bcc2ca1e3e825883d298793e04bd9c43a8
  updated_at: '2026-08-07T08:48:00.632247+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 3529
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 3529
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 3529
    cost_usd: 0.0
    recorded_at: '2026-08-07T08:52:53.895323+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-875__20260807T084857Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-768--task-OOMPAH-875
    source_sha: 6a84d9bcc2ca1e3e825883d298793e04bd9c43a8
    completed_at: '2026-08-07T08:52:53.909241+00:00'
---
## Summary

Live cutover regression on 2026-08-07: OOMPAH-865 was durably Ready at 08:33:01 with an idle validation broker, but no integration claim began until 08:41:29. The first post-cutover scheduler tick took 366 seconds, including 320 seconds in dispatch and 175 seconds in terminal-audit scanning/launch. _process_integration_queues is only scheduled after reconcile, review, dispatch, YOLO, and watchdog, so eligible exact-head delivery is starved behind unrelated slow lanes despite available validation capacity.

Implementation scope:
- Give durable shared-epic integration reconciliation its own promptly woken lane or schedule it before unrelated unbounded dispatch/audit work.
- Preserve one active integration pass, exact-head CAS authority, dependency ordering, project isolation, and the single validation-resource lease.
- Make submit/refresh/cutover events wake the integration lane without duplicate claims.
- Publish bounded latency/progress telemetry and an actionable alert only when an eligible row exceeds the configured claim bound.
- Keep terminal-audit, normal dispatch, and maintenance work from monopolizing integration progress.

Relevant code: oompah/orchestrator.py _tick and _process_integration_queues, event/refresh coalescing, integration_queue.py claiming, and state telemetry.

Required tests:
- A synthetic multi-minute dispatch/audit lane cannot delay an eligible Ready integration claim beyond the configured bound.
- Restart/cutover with a pre-existing Ready row starts exactly one integration pass.
- Concurrent submit/refresh events coalesce and never double-claim.
- Dependency-blocked rows remain blocked while an independent eligible row claims.
- Validation broker capacity and exact authority generation remain unchanged.

Acceptance criteria: a Ready integration row with satisfied dependencies and available validation capacity is claimed within a bounded interval independent of dispatch/audit duration; state exposes the last integration run/claim latency; no duplicate gate or lost wakeup occurs; focused scheduler/integration/event-loop tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 08:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 08:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 08:52
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 4, Tool calls: 0
- Tokens: 10 in / 3.5K out [3.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 3s
- Log: OOMPAH-875__20260807T084857Z.jsonl
---
author: oompah
created: 2026-08-07 09:25
---
Direct-owner claim active. Isolated OOMPAH-875 branch created from origin/main 39285e9c3. Implemented a dedicated, coalescing shared-epic integration lane with an isolated executor, prompt refresh/startup wakeups, and queue run/claim-latency telemetry. Added focused starvation, startup, and burst-coalescing regressions. Static compilation passes; focused pytest is blocked because this worktree has no configured test environment, and the validation broker remains occupied, so no full gate was started.
---
<!-- COMMENTS:END -->
