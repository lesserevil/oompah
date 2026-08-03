---
id: OOMPAH-745
type: task
status: In Progress
priority: 1
title: Add browser-level alert density and recovery regression coverage
parent: OOMPAH-740
children: []
blocked_by:
- OOMPAH-742
- OOMPAH-743
- OOMPAH-744
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T22:56:27.836890Z'
updated_at: '2026-08-03T23:33:15.475219Z'
work_branch: epic-OOMPAH-740--task-OOMPAH-745
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7ea5e0154cb84e897e182323a5c5ecb62c34b8624fe7e160c8ad4160013fc8d1
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T23:11:08.721622+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-745 describes a dedicated integration/regression\
    \ testing task that validates the *combined* alert experience under production-like\
    \ conditions \u2014 covering browser viewports, accessibility, recovery convergence,\
    \ layout bounds, and mixed payloads. The four active non-terminal peers in the\
    \ same epic are each implementation tasks with narrower, complementary scope:\n\
    Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\n\nEvidence: OOMPAH-745 describes a dedicated integration/regression\
    \ testing task that validates the *combined* alert experience under production-like\
    \ conditions \u2014 covering browser viewports, accessibility, recovery convergence,\
    \ layout bounds, and mixed payloads. The four active non-terminal peers in the\
    \ same epic are each implementation tasks with narrower, complementary scope:\n\
    \n- **OOMPAH-741** (In Progress) \u2014 server-side actionability contract: defines\
    \ structured alert fields and producer behavior; its tests cover producers and\
    \ snapshot construction, not browser-level harness integration.\n- **OOMPAH-742**\
    \ (Open) \u2014 UI implementation: replaces stacked banners with a compact alert\
    \ center; its required tests are scoped to that UI feature's own rendering states\
    \ (no/one/many alerts, collapse/expand), not the full production-payload combination\
    \ or accessibility suite that OOMPAH-745 describes.\n- **OOMPAH-743** (Open) \u2014\
    \ transcript sanitization: enforces length limits and redaction at both producer\
    \ and renderer boundaries; its tests cover sanitization correctness, not full-resync\
    \ convergence or viewport layout measurements.\n- **OOMPAH-744** (Open) \u2014\
    \ atomic stale-alert clearing: fixes the DOM lifecycle on WebSocket resync; its\
    \ tests cover specific convergence transitions, not the breadth of scenarios in\
    \ OOMPAH-745's acceptance criteria.\n\nOOMPAH-745 explicitly lists OOMPAH-742,\
    \ OOMPAH-743, and OOMPAH-744 as blockers, confirming it is the downstream integration\
    \ harness that proves the sibling implementations work correctly together. No\
    \ other active task in the corpus covers that role. All similarity-selected candidates\
    \ are Archived (terminal) and therefore excluded as duplicate targets. No active\
    \ duplicate exists."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 71bad1af-a2df-46bc-b654-108ea2047684
oompah.work_branch: epic-OOMPAH-740--task-OOMPAH-745
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-740--task-OOMPAH-745
  base_branch: epic-OOMPAH-740
  base_sha: 583fb236963493a820f36eabdd29789fa5497e6b
  updated_at: '2026-08-03T23:18:57.116048+00:00'
oompah.task_costs:
  total_input_tokens: 3
  total_output_tokens: 513
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 3
      output_tokens: 513
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 3
    output_tokens: 513
    cost_usd: 0.0
    recorded_at: '2026-08-03T23:11:08.719654+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-745__20260803T230737Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: duplicate_detector
    source_branch: epic-OOMPAH-740--task-OOMPAH-745
    source_sha: 583fb236963493a820f36eabdd29789fa5497e6b
    completed_at: '2026-08-03T23:11:08.738254+00:00'
---
## Summary

Add deterministic integration coverage proving that the complete alert experience remains compact, truthful, accessible, and convergent under production-like combinations of facts.

Scope:
- Extend the existing dashboard and WebSocket browser harnesses with representative alert payloads for integration rebase conflict, stale audit backlog, recovered auditor transport failure, running and failed quality gates, healthy repository hygiene, authentication policy denial, and genuine operator-actionable failures.
- Exercise a common desktop viewport matching the production screenshot and smaller responsive sizes.
- Verify initial load, incremental update, sequence-gap full resync, expand and collapse, many-alert overflow, task navigation, and recovery clearing.
- Assert semantic outcomes rather than fragile pixel snapshots where possible, while adding bounded layout measurements for alert-center height and board visibility.
- Include accessibility checks for disclosure state, focus order, alert announcements, and details access.
- Document any intentional presentation contract in existing user-facing dashboard documentation if operator behavior changes.

Relevant files: dashboard UI tests, WebSocket lifecycle and convergence tests, Granian end-to-end fixtures where applicable, and existing dashboard documentation.

Required tests and acceptance criteria:
- With the production-like mixed payload, the collapsed alert center remains bounded and the Kanban board is visible at initial render.
- Each underlying actionable fact appears once.
- Normal and healthy facts stay out of the actionable list.
- Expanding exposes sanitized details within an internally scrollable region.
- Recovery and full resync remove stale warnings without reload.
- No raw transcript appears in always-visible text.
- The full make test gate passes on the exact review-ready head.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 23:07
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-08-03 23:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 23:11
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 4, Tool calls: 0
- Tokens: 3 in / 513 out [516 total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 49s
- Log: OOMPAH-745__20260803T230737Z.jsonl
---
author: oompah
created: 2026-08-03 23:18
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-03 23:19
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-08-03 23:33
---
Understanding (Merge Conflict Resolver): Branch epic-OOMPAH-740--task-OOMPAH-745 currently has no unique commits — it is at the same HEAD as origin/epic-OOMPAH-740 (583fb2369). There are no merge conflicts to resolve. My scope is to: (1) fetch + rebase onto origin/epic-OOMPAH-740 (will be a no-op), (2) push the branch to origin to establish remote tracking, and (3) hand off to an implementation agent with the 'test' focus, since the actual work (writing browser-level alert density and recovery regression tests) has not started. Note: this task is blocked by OOMPAH-742, OOMPAH-743, and OOMPAH-744 which are also in the same not-yet-implemented state.
---
<!-- COMMENTS:END -->
