---
id: OOMPAH-657
type: task
status: Open
priority: null
title: Run branch quality gates from immutable exact-head snapshots
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T11:06:15.542774Z'
updated_at: '2026-07-31T11:08:44.113496Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 156eeba91c00cafe17da43dbf88f58a7e3e04e766e328754b828313bb3033357
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T11:08:39.612047+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive search of the oompah task tracker, I can now\
    \ provide my duplicate investigation verdict.\n\n## Investigation Summary\n\n\
    I searched for existing tasks that might duplicate OOMPAH-657 (\"Run branch quality\
    \ gates from immutable exact-head snapshots\") using multiple approaches:\n\n\
    1. **Keyword searches** across `.oompah/tasks/`:\n   - Quality gate terms: `quality_gate`,\
    \ `gate`, `exact-head`, `immutable`, `snapshot`\n   - Race condition terms: `race`,\
    \ `mutation`, `moving`, `worktree.reassign`, `reopen`\n   - Related domains: `integration`,\
    \ `review`, `orchestration`\n\n2. **Task state search**:\n   - Examined all `open/`\
    \ tasks (1 task - OOMPAH-281, unrelated)\n   - Examined all `backlog/` tasks (1\
    \ task - OOMPAH-282, unrelated)\n   - Noted all `merged/` and `archived/` tasks\
    \ are terminal states and excluded from consideration\n\n3. **Direct dependency\
    \ check**:\n   - OOMPAH-655 referenced in coordination note as dependency \u2014\
    \ **does not exist** in `.oompah/tasks`\n   - OOMPAH-655 is mentioned as the incident\
    \ where the race was reproduced (\"Live race reproduced on OOMPAH-655 at 2026-07-31\
    \ 11:03-11:06 UTC\")\n\n4. **Code validation**:\n   - Confirmed `oompah/quality_gate.py`\
    \ exists (current implementation)\n   - No other quality-gate-related tasks found\
    \ in tracker\n\n## Findings\n\n**No active duplicate task exists.** The only referenced\
    \ related task (OOMPAH-655) is not present in the native oompah task tracker.\
    \ It either:\n- Has not yet been filed as a native task (may be tracked externally)\n\
    - Is the incident report from which OOMPAH-657 is derived\n- Will be filed as\
    \ a separate dependency task\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Comprehensive search of `.oompah/tasks` across all non-terminal states (open,\
    \ backlog) found no existing tasks addressing quality gates, immutable snapshots,\
    \ exact-head verification, worktree mutation race conditions, or integration launch\
    \ paths. The sole mentioned d"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 005e2645-9191-48ef-ae8e-a39a4acf1a4c
oompah.task_costs:
  total_input_tokens: 186
  total_output_tokens: 5176
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 186
      output_tokens: 5176
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 186
    output_tokens: 5176
    cost_usd: 0.0
    recorded_at: '2026-07-31T11:08:39.611070+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-657__20260731T110710Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-657
    source_sha: 54dd2509c6cbc73aaadbda2a3fdc7cfbb14530eb
    completed_at: '2026-07-31T11:08:39.620340+00:00'
---
## Summary

Live race reproduced on OOMPAH-655 at 2026-07-31 11:03-11:06 UTC: a full gate launched for submitted head 2713e14ea continued in the task's reusable worktree after operator rejection/reopen, while the replacement implementation agent modified oompah/quality_gate.py and tests in that same worktree. Pytest therefore read a moving mixture that did not correspond to the recorded head, yet the result could still be consumed as exact-head evidence. Implementation scope: change the server-owned quality-gate/integration launch path and worktree lifecycle so every gate executes from an immutable snapshot of the recorded commit (dedicated detached worktree, archive, or equivalent), with the checked-out SHA verified before spawn; prevent task worktree reassignment/mutation from affecting an active gate; tie cancellation and process-group cleanup to the exact gate generation; and discard results when task/head/generation is no longer current. Relevant code includes oompah/quality_gate.py, integration/review orchestration, worktree allocation/cleanup, and their tests. Add deterministic barrier tests that start a gate, reopen and edit/reassign the normal task worktree, then prove the gate sees only its recorded head; cover old/new head gates overlapping, cancellation/rejection before completion, stale success never creating a review/integration, exact owned-descendant cleanup, and snapshot cleanup without pruning active evidence. Acceptance: a gate result is cryptographically/topologically attributable to one immutable commit, mutable task worktrees can never change its inputs, stale generations have no state effect, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 11:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 11:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 11:08
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 51, Tool calls: 22
- Tokens: 186 in / 5.2K out [5.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 33s
- Log: OOMPAH-657__20260731T110710Z.jsonl
---
<!-- COMMENTS:END -->
