---
id: OOMPAH-744
type: bug
status: In Progress
priority: 1
title: Atomically clear stale alert UI after authoritative resynchronization
parent: OOMPAH-740
children: []
blocked_by:
- OOMPAH-741
- OOMPAH-742
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T22:56:25.203763Z'
updated_at: '2026-08-03T23:17:47.828254Z'
work_branch: epic-OOMPAH-740--task-OOMPAH-744
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e0ed13f89f5d9474cda2cf090ec12b8e89669c6301513c4104c19a76df20ecb5
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T23:06:20.605143+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed all 5 required peer tasks (OOMPAH-740 through\
    \ OOMPAH-745, all included in corpus with 0 omissions). OOMPAH-744 addresses DOM\
    \ lifecycle and state reconciliation for alert clearing after resynchronization,\
    \ while peers address complementary concerns: server-side alert classification\
    \ (741), UI structure consolidation (742), content sanitization (743), and regression\
    \ testing (745). Each task is technically distinct with no overlap in implementation\
    \ scope.\n# Duplicate Investigation: OOMPAH-744\n\nLet me analyze whether OOMPAH-744\
    \ is a duplicate of any existing active task using only the supplied project task\
    \ corpus.\n\n## Analysis\n\n**OOMPAH-744** focuses specifically on: **Atomically\
    \ clearing stale alert UI when the dashboard receives an authoritative full state**,\
    \ particularly after WebSocket sequence gaps. The task emphasizes DOM lifecycle\
    \ and state reconciliation at the UI layer.\n\n**Reviewing required peer tasks\
    \ (all included in corpus, none omitted):**\n\n1. **OOMPAH-741** (Open, Bug):\
    \ \"Classify dashboard facts by current operator actionability\"\n   - Scope:\
    \ Server-side presentation contract definition\n   - Focus: What facts should\
    \ trigger actionable warnings\n   - Not about: DOM clearing or UI lifecycle\n\n\
    2. **OOMPAH-742** (Open, Feature): \"Replace stacked dashboard banners with a\
    \ compact alert center\"\n   - Scope: Visual layout and UI structure redesign\n\
    \   - Focus: Consolidating alert panels into single compact container\n   - Not\
    \ about: Clearing stale state or DOM synchronization\n\n3. **OOMPAH-743** (Open,\
    \ Bug): \"Keep raw failure transcripts out of dashboard alert summaries\"\n  \
    \ - Scope: Content sanitization and truncation\n   - Focus: Formatting alert messages\
    \ safely\n   - Not about: Clearing or DOM state management\n\n4. **OOMPAH-745**\
    \ (Open, Task): \"Add browser-level alert density and recovery regression coverage\"\
    \n   - Scope: Testing infrastructure and regression coverage\n   - Focus: Proving\
    \ alert behavior under production scenarios\n   - Not about: Implementation of\
    \ clearing mechanism\n\n5. **OOMPAH-740** (Decomposed, Epic): \"Make dashboard\
    \ alerts compact, truthful, and non-blocking\"\n   - Status: Parent epic of OOMPAH-744\n\
    \   - Not a duplicate; structural parent relationship\n\n## Conclusion\n\nEach\
    \ peer task addresses a distinct aspect of the alert system lifecycle:\n- **OOMPAH-741**:\
    \ Alert classification (server decision logic)\n- **OOMPAH-742**: Alert container\
    \ UI structure (layout)\n- **OOMPAH-743**: Alert content formatting (sani"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: dbab9525-8a8a-4f37-aca1-7492a2d37d0b
oompah.work_branch: epic-OOMPAH-740--task-OOMPAH-744
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-740--task-OOMPAH-744
  base_branch: epic-OOMPAH-740
  base_sha: 583fb236963493a820f36eabdd29789fa5497e6b
  updated_at: '2026-08-03T23:15:36.994182+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1994
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1994
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1994
    cost_usd: 0.0
    recorded_at: '2026-08-03T23:06:20.603456+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-744__20260803T230325Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-740--task-OOMPAH-744
    source_sha: 583fb236963493a820f36eabdd29789fa5497e6b
    completed_at: '2026-08-03T23:06:20.621019+00:00'
---
## Summary

Make alert and health presentation converge atomically whenever the dashboard receives an authoritative full state, including after a detected WebSocket sequence gap.

This task builds on OOMPAH-691 through OOMPAH-695. It does not redesign the sequencing protocol; it fixes the alert-derived DOM lifecycle that consumes the converged snapshot.

Scope:
- Treat every authoritative snapshot as a replacement for all alert, terminal-audit, quality-gate, authentication, and repository-health presentation state.
- Remove panels, list items, counts, badges, and stale CSS state for facts absent from the replacement snapshot.
- Prevent mixed-generation rendering where a new generic alert list is displayed beside old dedicated health panels.
- During Synchronizing state, keep the last known board usable, label its freshness compactly, and avoid presenting old warning facts as current after the replacement is available.
- Make incremental updates and full replacements share stable identity and ordering rules.
- Add bounded diagnostics for a presentation replacement failure without generating warning loops.

Relevant files: dashboard WebSocket and handleStateUpdate logic in oompah/templates/dashboard.html, full-sync response handling in oompah/server.py if needed, and OOMPAH-691 through OOMPAH-695 test harnesses.

Required tests:
- Transport failure to recovered zero removes every old failure rendering without refresh.
- Failed quality gate to running or idle replaces the old panel atomically.
- Dropped or reordered messages trigger full sync and leave exactly the authoritative alert set.
- A service epoch change cannot retain old alert DOM.
- Repeated identical snapshots do not duplicate alerts or announcements.

Acceptance criteria:
- After successful resynchronization, the browser alert center and status view exactly match the authoritative snapshot.
- No stale failure remains visible alongside recovered live state.
- Normal gap recovery remains non-alerting as specified by OOMPAH-695.
- Focused WebSocket, state reconciliation, and dashboard tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 23:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 23:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 23:06
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 33s
- Log: OOMPAH-744__20260803T230325Z.jsonl
---
author: oompah
created: 2026-08-03 23:15
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 23:15
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 23:17
---
UNDERSTANDING: This task requires fixing the dashboard's WebSocket state handling to atomically replace alert and health presentation state whenever an authoritative full snapshot is received. Key requirements:

1. Treat authoritative snapshots as complete replacements (not merges)
2. Remove stale UI elements (panels, list items, counts, badges) for absent facts
3. Prevent mixed-generation rendering during Synchronizing state
4. Share stable identity/ordering between incremental and full updates
5. Add bounded diagnostics for replacement failures

The fix focuses on dashboard.html WebSocket handling and potentially server.py full-sync response. Related prior work: OOMPAH-691 through OOMPAH-695.

Plan: (1) Explore relevant code, (2) Understand current state handling, (3) Implement atomic replacement logic, (4) Test all required scenarios, (5) Ensure no regressions.
---
<!-- COMMENTS:END -->
