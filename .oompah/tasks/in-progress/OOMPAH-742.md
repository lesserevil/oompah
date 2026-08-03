---
id: OOMPAH-742
type: feature
status: In Progress
priority: 1
title: Replace stacked dashboard banners with a compact alert center
parent: OOMPAH-740
children: []
blocked_by:
- OOMPAH-741
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T22:56:17.550824Z'
updated_at: '2026-08-03T23:09:53.099631Z'
work_branch: epic-OOMPAH-740--task-OOMPAH-742
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6380acf6cb02a369f8a5d0ac580523b98cd20810c4347ded4c5d30e0e753180c
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T23:05:48.889370+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: OOMPAH-742 is an open feature task and explicit child decomposition
    of epic OOMPAH-740 ("Make dashboard alerts compact, truthful, and non-blocking").
    It focuses on the frontend UI implementation of a consolidated alert center component
    for oompah/templates/dashboard.html. The four sibling tasks (OOMPAH-741, 743,
    744, 745) address related but distinct concerns: backend data contract, transcript
    sanitization, WebSocket/DOM reconciliation, and regression testing respectively.
    No archived task describes this UI component work. The task is unique and represents
    legitimate new implementation work that depends on completion of OOMPAH-741''s
    backend contract.

    I need to investigate whether OOMPAH-742 is a duplicate of an existing issue by
    comparing it with the supplied task corpus.


    ## Analysis


    Let me examine OOMPAH-742 and compare it with potentially related tasks in the
    corpus:


    **OOMPAH-742** (Current task, Open):

    - Title: "Replace stacked dashboard banners with a compact alert center"

    - Type: Feature

    - Scope: Frontend UI implementation to consolidate dashboard alerts into a single
    compact, collapsible alert center

    - Relevant files: oompah/templates/dashboard.html and dashboard UI tests

    - Blocked by OOMPAH-741 (backend data structure)


    **Parent Epic OOMPAH-740** (Decomposed):

    - Title: "Make dashboard alerts compact, truthful, and non-blocking"

    - This is the parent epic that OOMPAH-742 decomposes from

    - Focus: Overall dashboard alert strategy and architecture

    - OOMPAH-742 is explicitly listed as a child task with distinct scope


    **Related Sibling Tasks** (OOMPAH-741, 743, 744, 745 - all Open):

    - OOMPAH-741: Backend server-side presentation contract (dependency)

    - OOMPAH-743: Sanitize transcript output (focused on content safety)

    - OOMPAH-744: WebSocket state reconciliation for stale alerts (focused on data
    consistency)

    - OOMPAH-745: Regression test coverage (focused on testing)


    Each of these is clearly scoped to a different aspect:

    - OOMPAH-741 defines the backend data contract

    - OOMPAH-742 implements the frontend UI/UX (the alert center component, collapsible
    state, scrolling, layout)

    - OOMPAH-743 ensures transcripts are sanitized

    - OOMPAH-744 handles DOM lifecycle when state updates

    - OOMPAH-745 provides regression coverage


    **Terminal/Archived Tasks Review**:

    All 181 archived tasks in the corpus cover unrelated areas (tracker issues, release
    management, epic workflow, documentation). None describe an existing implementation
    of a compact dashboard alert center.


    ---


    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: OOMPAH-742 is an open feature task and explicit'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 6107abe9-9a31-45d4-8323-44673d52a6d0
oompah.work_branch: epic-OOMPAH-740--task-OOMPAH-742
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-740--task-OOMPAH-742
  base_branch: epic-OOMPAH-740
  base_sha: 583fb236963493a820f36eabdd29789fa5497e6b
  updated_at: '2026-08-03T23:09:48.429420+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1766
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1766
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1766
    cost_usd: 0.0
    recorded_at: '2026-08-03T23:05:48.879981+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-742__20260803T230137Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-740--task-OOMPAH-742
    source_sha: 583fb236963493a820f36eabdd29789fa5497e6b
    completed_at: '2026-08-03T23:05:48.946971+00:00'
---
## Summary

Replace the current collection of always-visible warning and health banners with one compact operator alert center while preserving access to all relevant information.

Scope:
- Remove the duplicate generic rendering in the agent bar and Oompah alerts banner.
- Render a single collapsed summary showing the actionable count and highest severity, with a clear control to expand details.
- Enforce a strict viewport-relative maximum height and internal scrolling for expanded details so the Kanban board retains meaningful visible space.
- Move healthy repository inventory, running quality gates, normal audit throughput, authentication status, and other non-actionable facts into a compact status or diagnostics view that does not displace the board.
- Render each stable alert identity once even if multiple legacy fields contain it during migration.
- Preserve responsive layout, existing board scroll owners, drag and drop, dynamic appearance and clearing, keyboard navigation, focus management, and aria-live behavior without repeatedly announcing full transcripts.

Relevant files: oompah/templates/dashboard.html and dashboard UI tests under tests/.

Required tests:
- No alerts, one alert, many alerts, mixed severity, and expanded or collapsed states.
- Duplicate generic and dedicated health facts render once.
- The board remains visible and scrollable at common desktop viewport heights.
- Dynamic alert addition and removal does not corrupt layout or focus.
- Keyboard and accessible-name assertions cover the disclosure control and alert list.

Acceptance criteria:
- The default dashboard view is board-first, not alert-first.
- Alerts consume at most the compact summary height until an operator explicitly expands them.
- Expanded details are bounded and independently scrollable.
- No condition is repeated in both the agent bar and a banner.
- Focused dashboard tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 23:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 23:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 23:05
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.8K out [1.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 47s
- Log: OOMPAH-742__20260803T230137Z.jsonl
---
author: oompah
created: 2026-08-03 23:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 23:09
---
Focus: Frontend Developer
---
<!-- COMMENTS:END -->
