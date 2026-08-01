---
id: OOMPAH-679
type: bug
status: In Progress
priority: 1
title: Reset activity panel identity when a task starts a new agent run
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T12:05:24.382952Z'
updated_at: '2026-08-01T14:34:39.263427Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c2afc418e9d217abf284d9e8a66ead0db5aec54a956ab1276d9a2e851c9b6bfe
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T14:33:49.231152+00:00'
  matched_identifiers: []
  evidence: 'Based on my comprehensive search of the oompah task tracker, I''ve completed
    the duplicate investigation for OOMPAH-679. Let me summarize my findings:


    **Investigation Summary:**


    I searched for related tasks using multiple approaches:

    1. Searched `.oompah/tasks/open/`, `.oompah/tasks/backlog/` - found OOMPAH-281
    (self-hosted runners) and OOMPAH-282 (unicode encoding error) - neither related

    2. Reviewed all merged tasks (OOMPAH-271, 272, 275, 277-280) - all about epic
    rebasing or CI runner setup, none about activity panel or run identity

    3. Searched source code (oompah/) and plans/ for keywords: activity, panel, dashboard,
    running snapshot, run identity, focus_name, focus_role - no matches in active
    code planning

    4. Verified the issue describes a specific live UI regression observed on 2026-08-01
    for task EXOCOMP-143, where the dashboard activity panel failed to reset when
    transitioning from Duplicate Investigator run to Maintenance Engineer run


    **Key Evidence:**

    - OOMPAH-679 is about a regression where activity panel state is keyed by `issue_identifier`
    alone, not by per-run identity

    - The issue requires architectural changes to: expose stable per-run identity,
    reset panel title/cached entries/activity by run_id, handle late activity from
    superseded runs

    - No existing open, backlog, or recent merged tasks cover this specific problem

    - The issue is marked Priority 1, indicating it''s a critical regression

    - Previous comments show duplicate screening was already initiated


    ---


    **Focus handoff: duplicate_detector**


    **Duplicate preflight verdict: no_duplicate**


    **Matches: none**


    **Evidence:** Extensive search of `.oompah/tasks` (open, backlog, merged, archived),
    source code plans/, and implementation files found no existing active task covering
    the activity panel identity reset issue. OOMPAH-281 (self-hosted runners) and
    OOMPAH-282 (unicode error) in open/backlog are unrelated. All merged tasks (271,
    272, 275-280) address epic rebasing or CI infrastructure, not dash'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 6ab016d9-736a-4cb7-b1cf-087d504bdbee
oompah.task_costs:
  total_input_tokens: 202
  total_output_tokens: 5482
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 202
      output_tokens: 5482
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 202
    output_tokens: 5482
    cost_usd: 0.0
    recorded_at: '2026-08-01T14:33:49.201952+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-679__20260801T143153Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-679
    source_sha: 62ca0ca696d08b754e03a200d7227455786da960
    completed_at: '2026-08-01T14:33:49.270886+00:00'
---
## Summary

Live UI regression observed for EXOCOMP-143 on 2026-08-01. A read-only Duplicate Investigator run completed normally at 11:58 with a no-duplicate verdict and zero mutating tool calls. Oompah immediately started a distinct implementation run for the same task with focus_name=chore and focus_role=Maintenance Engineer. The dashboard activity panel continued to show 'Agent: EXOCOMP-143 — Duplicate Investigator · default' while rendering the implementation run's activity, making it appear that the preflight agent violated its role. The client and activity route primarily key state by issue_identifier, which is reused across run boundaries. Implementation scope: expose a stable per-run identity/run id in running snapshots and activity responses; key/reset panel title, cached entries, provider metadata, and polling/WebSocket activity by that identity; update the title even during the brief empty-focus startup state; reject or ignore late activity from superseded runs. Relevant files: orchestrator RunningEntry serialization, /api/v1/state, /api/v1/agents/{identifier}/activity, dashboard activity state/rendering, and WebSocket lifecycle tests. Acceptance criteria: a duplicate-preflight-to-implementation transition on the same task never mixes labels or activity; the old run visibly ends before the new role appears; late old-run events cannot overwrite the new panel; regression coverage reproduces the rapid EXOCOMP-143 transition.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 14:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 14:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 14:33
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 67, Tool calls: 36
- Tokens: 202 in / 5.5K out [5.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 0s
- Log: OOMPAH-679__20260801T143153Z.jsonl
---
author: oompah
created: 2026-08-01 14:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 14:34
---
Focus: Frontend Developer
---
<!-- COMMENTS:END -->
