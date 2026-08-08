---
id: OOMPAH-907
type: bug
status: In Progress
priority: 1
title: Serialize orphan recovery with epic rollup authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T06:36:33.809062Z'
updated_at: '2026-08-08T06:40:18.881505Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: cef7ecf12f50cd49b37e5292bdee1f79f0d9fc05bba449714f9ce4834bbdafeb
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-08T06:39:38.719797+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Duplicate preflight verdict: no_duplicate\nMatches: none\n\
    I'll now analyze OOMPAH-907 as a Duplicate Investigator by comparing it with the\
    \ supplied project task corpus.\n\n## Analysis\n\n**OOMPAH-907 Issue Summary:**\n\
    - **Problem**: OOMPAH-795 oscillates between In Progress \u2194 Open due to a\
    \ race condition where orphan recovery resets an accepted-code parent (finding\
    \ no running agent), then epic rollup immediately restores In Progress (because\
    \ child OOMPAH-859 is non-terminal).\n- **Required Fix**: Implement authoritative\
    \ reconciliation to prevent orphan recovery from resetting a rollup parent whose\
    \ child lineage legitimately owns non-terminal status, and prevent parent rollup\
    \ from racing a newer direct-owner/recovery decision.\n- **Key Scope**: Stalled-task\
    \ watchdog/orphan recovery, epic/native parent rollup, WorkDecision generation,\
    \ task-transition serialization.\n\n**Corpus Review:**\n\nI reviewed all 34 similarity\
    \ candidates provided in the authoritative task corpus. All candidates share thematic\
    \ overlap with oompah's orchestration, task states, epic workflows, or agent safety,\
    \ but **none describe the core issue**: the serialization race between orphan\
    \ recovery and epic rollup for parent state transitions.\n\n**Closest Reviewed\
    \ (All Terminal):**\n- **OOMPAH-219** (Archived): Shared-worktree commit races\
    \ \u2014 different race condition (two children on same branch, not parent/child\
    \ rollup authority).\n- **OOMPAH-218** (Archived): Incomplete-agent safety limits\
    \ \u2014 about per-focus session counting, not parent-child state serialization.\n\
    - **OOMPAH-165** (Archived): Epic landed detection \u2014 about detecting epic\
    \ branch merges to default, not parent/child rollup conflicts.\n- **OOMPAH-168**\
    \ (Archived): Orchestration simplification \u2014 removed flat/stacked strategies,\
    \ not parent-rollup authority.\n\n**Active Non-Terminal Tasks:**\n- **OOMPAH-787**\
    \ (In Progress): \"Complete shadow/enforce rollout\" \u2014 unrelated feature\
    \ (configuration flags and upgrade paths).\n- **OOMPAH-907** (current task, Open):\
    \ This task.\n\nNo active open or in-progress task covers orphan-re"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: ed409d99-6aad-456f-a501-895519fe3f5a
oompah.work_contributors:
  runs:
  - run_id: 3d010ee020b44d19b140288b64f7d798--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-907
    source_sha: bb82f7f39510f0e02886307291812f2f8b3e6901
    completed_at: '2026-08-08T06:39:38.750099+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1699
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1699
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1699
    cost_usd: 0.0
    recorded_at: '2026-08-08T06:39:38.718271+00:00'
---
## Summary

Triggered by: OOMPAH-795

Live OOMPAH-795 repeatedly oscillates In Progress -> Open -> In Progress with no running agent and no owner claim: orphan recovery resets the accepted-code parent because it sees no worker, then epic rollup immediately restores In Progress because child OOMPAH-859 is non-terminal. The loop emits possible-state-loop warnings and at least 50 consecutive epic_rollup_parent rejections while doing no work. Implement one authoritative reconciliation rule/transaction so orphan recovery cannot reset a rollup parent whose child lineage or accepted integration evidence legitimately owns its non-terminal status, and so parent rollup cannot race a newer direct-owner/recovery decision. Relevant areas: stalled-task watchdog/orphan recovery, epic/native parent rollup, WorkDecision generation and task-transition serialization. Add a production-shaped OOMPAH-795 regression with an accepted parent head, no live agent, and one active child; prove repeated concurrent ticks converge to one truthful stable status, produce no loop warning, preserve dispatch for a genuinely orphaned leaf, and recover normally once the child terminalizes. Acceptance: no Open/In Progress oscillation, no false agent activity, exact owner/generation fencing remains fail-closed, and focused watchdog/epic-rollup/workflow plus full make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 06:38
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-08 06:38
---
Live evidence captured on 2026-08-08: OOMPAH-795 has no running agent and no owner claim. Orphan recovery changes In Progress to Open, then native epic rollup restores In Progress because OOMPAH-859 is non-terminal; this repeats approximately every two minutes and logs possible-state-loop plus 50 consecutive epic_rollup_parent rejections. Promoted to Open for direct repair after the systemic composition gate stabilizes.
---
author: oompah
created: 2026-08-08 06:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-08 06:39
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 2s
- Log: OOMPAH-907__20260808T063909Z.jsonl
---
<!-- COMMENTS:END -->
