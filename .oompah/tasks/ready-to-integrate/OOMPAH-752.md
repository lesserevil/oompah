---
id: OOMPAH-752
type: bug
status: Ready to Integrate
priority: 1
title: Select standalone Ready delivery fairly before claiming task authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T01:54:29.023994Z'
updated_at: '2026-08-04T02:23:11.697811Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2105cbf83e227c5f8aa8ce20a9cfd2a23154e4e3a636a4be88f9ce298c0da803
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T01:59:42.868479+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** All 30 similarity candidates in the project corpus\
    \ are archived (terminal state). The standalone Ready delivery LIFO starvation\
    \ bug is unique and active. No peer task in the corpus\u2014archived or otherwise\u2014\
    describes the same underlying problem of fair scheduling for simultaneous eligible\
    \ standalone Ready tasks with FIFO ordering and bounded delivery turns.\nI'm reviewing\
    \ OOMPAH-752 for duplicate classification using the supplied project task corpus.\
    \ Let me analyze this systematically.\n\n## Analysis\n\n**Current Task (OOMPAH-752):**\n\
    - Title: \"Select standalone Ready delivery fairly before claiming task authority\"\
    \n- Status: Open (active, not terminal)\n- Type: Bug (LIFO starvation regression)\n\
    - Core issue: Standalone Ready tasks are being delivered in reverse chronological\
    \ order (newest first) instead of FIFO, causing indefinite starvation of older\
    \ eligible tasks\n\n**Corpus Search Results:**\nThe supplied corpus contains 30\
    \ similarity candidates, all of which are in terminal state (Archived). These\
    \ archived tasks cover:\n- Native tracker/GitHub intake improvements (OOMPAH-10\
    \ through OOMPAH-15)\n- Error handling and UI enhancements (OOMPAH-156 through\
    \ OOMPAH-161)\n- Epic workflow standardization (OOMPAH-164 through OOMPAH-171)\n\
    - Release-branch addendum implementation (OOMPAH-172 through OOMPAH-187)\n- Dashboard\
    \ filtering (OOMPAH-187)\n- Git operations (OOMPAH-270)\n\n**Assessment:**\nNone\
    \ of the archived tasks in the corpus address the specific standalone Ready delivery\
    \ LIFO starvation bug described in OOMPAH-752. The archived tasks touch related\
    \ orchestration, epic workflows, and integration mechanics, but not the specific\
    \ fair-scheduling regression where:\n1. Multiple eligible standalone Ready tasks\
    \ exist simultaneously\n2. Older tasks are superseded/cancelled before review\
    \ lookup\n3. Only the newest task reaches capacity check and full quality gate\n\
    4. This creates effectively LIFO delivery ordering\n\nThe corpus metadata indicates\
    \ `required_peer_count: 0` (no structural peers identified) and all 30 similarity\
    \ candidates are terminal (Archived), meaning there are no active tasks representing\
    \ this specific bug.\n\n---\n\n**Focus handoff: duplicate_detector**\n\n**Duplicate\
    \ preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:** All\
    \ 30 similarity candidates in the project corpus are archived (terminal state).\
    \ The standalone Ready deli"
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
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1899
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1899
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1899
    cost_usd: 0.0
    recorded_at: '2026-08-04T01:59:42.860844+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-752__20260804T015847Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-752
    source_sha: 18e18a6b63b2f9a522b17c0132dac0f5a0d9e487
    completed_at: '2026-08-04T01:59:43.055027+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-752
  head_sha: 45fd50c6f56f22d8195ee2cb67ab84c57918d5ac
  submitted_at: '2026-08-04T02:15:14.140879+00:00'
  updated_at: '2026-08-04T02:15:14.140879+00:00'
---
## Summary

Triggered by: OOMPAH-749

Live regression on revision c54a60a6, which already contains OOMPAH-732. After PR 698 freed Oompah review capacity, standalone Ready tasks OOMPAH-735, OOMPAH-746, OOMPAH-748, OOMPAH-749, and OOMPAH-750 were all eligible. Each sweep logged Cancelled superseded standalone delivery before review lookup for the older tasks, while only newest OOMPAH-750 reached the capacity check and started the full quality gate. This makes delivery effectively LIFO and permits indefinite starvation when Ready work continues arriving; OOMPAH-749 is the live queue-recovery fix whose delay leaves 37 shared integration rows at attempts=0. Implementation scope: build the eligible standalone set first, resolve dependencies and review or gate capacity once, and select a bounded candidate with stable priority plus FIFO submitted-at ordering before claiming delivery authority or doing remote work. Do not issue and revoke authorities for unselected tasks; retain a truthful non-actionable capacity-wait state. If the selected candidate is invalid or undeliverable, record its actionable reason and consider the next eligible candidate in the same bounded sweep. Preserve exact-head fencing, existing-review adoption, per-project capacity, same-head retry, dependency ordering, and OOMPAH-732 separation from shared queue processing. Relevant code: _reconcile_standalone_ready_to_integrate_tasks, standalone authority claim and refresh, Ready tracker ordering, BranchQualityGate ownership, and review-capacity reservations. Required tests: five simultaneous Ready tasks where the oldest eligible task gates first; continuous new arrivals cannot overtake an older row; high priority precedes lower priority with FIFO ties; dependency-blocked and invalid-head rows do not block the next eligible task; list/detail representations remain authority-equivalent; restart, existing PR, gate failure, and capacity wait. Acceptance criteria: every eligible standalone Ready task receives a bounded delivery turn without LIFO starvation, unselected tasks are not reported as superseded, and OOMPAH-749 can reach review without manual delivery.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 01:58
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 01:58
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 01:59
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 12s
- Log: OOMPAH-752__20260804T015847Z.jsonl
---
author: oompah
created: 2026-08-04 02:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 02:01
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-08-04 02:01
---
Understanding: I will inspect standalone Ready reconciliation, candidate ordering, dependency/head validation, authority claims, and capacity handling. I will implement bounded stable selection with priority/FIFO ordering and add regression tests for starvation, invalid candidates, capacity waits, and existing behavior.
---
author: oompah
created: 2026-08-04 02:07
---
Discovery/implementation: staged standalone candidates without authority claims, sorted by priority then submitted-at FIFO, and limited delivery ownership to the selected candidate. Invalid candidates fall through to the next ordered row; project capacity is checked once per sweep and selected capacity waits remain informational. Existing exact-head, review adoption, gate, reservation, and queue paths remain in place.
---
author: oompah
created: 2026-08-04 02:12
---
Verification: focused standalone reconciliation plus review-capacity and integration-queue suites pass: 60 tests. Coverage now includes priority/FIFO selection, oldest-row fallback on invalid remote branches, dependency-blocked fallback, no claims for unselected rows, and informational capacity waits; existing restart, review adoption, exact-head, gate, and reservation tests remain green.
---
author: oompah
created: 2026-08-04 02:13
---
Verification update: after adding the concurrent reservation safeguard, the focused standalone, review-capacity, and integration-queue suites remain green (60 passed). No lower-ranked candidate is claimed or gated after a selected candidate loses the shared review slot.
---
author: oompah
created: 2026-08-04 02:15
---
Completion: delivered fair standalone Ready selection on the pushed branch. Candidates are staged without unselected authority claims, ordered by priority and submitted-at FIFO, invalid rows fall through within the snapshot, and capacity waits remain informational and retry-safe. Existing review adoption, exact-head fencing, dependency ordering, restart/retry, gate, and per-project reservation behavior are preserved. Final focused verification: 60 passed.
---
author: oompah
created: 2026-08-04 02:15
---
Fair standalone Ready delivery selection with priority/FIFO ordering, bounded fallback, and truthful capacity waits; 60 focused tests pass.
---
author: oompah
created: 2026-08-04 02:15
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 76
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 14m 33s
- Log: OOMPAH-752__20260804T020117Z.jsonl
---
author: oompah
created: 2026-08-04 02:23
---
Branch quality gate passed for `45fd50c6f56f22d8195ee2cb67ab84c57918d5ac` using `make test` in 413.1s. Review creation may proceed.
---
<!-- COMMENTS:END -->
