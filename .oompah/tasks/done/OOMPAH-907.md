---
id: OOMPAH-907
type: bug
status: Done
priority: 1
title: Serialize orphan recovery with epic rollup authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T06:36:33.809062Z'
updated_at: '2026-08-09T05:10:29.201862Z'
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
oompah.agent_run_id: 62b1144b-219d-4b43-94f7-cebd72b849c7
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
  - run_id: 011de4628a504e1d9012ede656b2bf19--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-907
    source_sha: null
    completed_at: ''
  - run_id: bb8575f00f2d4f34b04349d4bb0918c3--contributor-9efe7fcc211b
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: general
    source_branch: OOMPAH-907
    source_sha: null
    completed_at: ''
  - run_id: f04915a137d04ff7a6784e8698a3f7fc--contributor-9efe7fcc211b
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: general
    source_branch: OOMPAH-907
    source_sha: null
    completed_at: ''
  - run_id: ece7f9b25da94076965c6ab7b9709851--contributor-9efe7fcc211b
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: general
    source_branch: OOMPAH-907
    source_sha: null
    completed_at: ''
  - run_id: 5a50a24f4625441c9937068a8321e91f--contributor-9efe7fcc211b
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: general
    source_branch: OOMPAH-907
    source_sha: null
    completed_at: ''
  - run_id: 5dbfc041932e4ec5877a6b6ac416f940--contributor-9efe7fcc211b
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: general
    source_branch: OOMPAH-907
    source_sha: null
    completed_at: ''
  - run_id: 612d53cdfbeb4c6786cb198499d51b5b--contributor-9efe7fcc211b
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: general
    source_branch: OOMPAH-907
    source_sha: null
    completed_at: ''
  - run_id: f74c1682eaa94b3cad0da3faa0845997--contributor-9efe7fcc211b
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: general
    source_branch: OOMPAH-907
    source_sha: null
    completed_at: ''
  - run_id: 8a9c833da5f64093886659bec156aea5--contributor-9efe7fcc211b
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: general
    source_branch: OOMPAH-907
    source_sha: null
    completed_at: ''
  - run_id: 3634380661ea4761979db2e239694129--contributor-9efe7fcc211b
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: general
    source_branch: OOMPAH-907
    source_sha: null
    completed_at: ''
  - run_id: 5d54dda07a994ca0a21becd1dbc206d6--contributor-9efe7fcc211b
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: general
    source_branch: OOMPAH-907
    source_sha: null
    completed_at: ''
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
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-3efb70f2bc7d
    project_id: proj-14849f1b
    task_id: OOMPAH-907
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 55393f26938b1e448d5ea962cb8dcfdc8957f7519cd7b53e1f8a275e26d54ecf
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:10:25.218980+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
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
author: oompah
created: 2026-08-08 06:40
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-08 06:40
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-08 06:41
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-08 06:41
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 49s
- Log: OOMPAH-907__20260808T064049Z.jsonl
---
author: oompah
created: 2026-08-08 06:41
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-08 06:41
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-08 06:42
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 20s (attempt #2)
---
author: oompah
created: 2026-08-08 06:42
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 31s
- Log: OOMPAH-907__20260808T064158Z.jsonl
---
author: oompah
created: 2026-08-08 06:42
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-08-08 06:43
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-08 06:43
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 40s (attempt #3)
---
author: oompah
created: 2026-08-08 06:43
---
Run #3 [attempt=3, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 31s
- Log: OOMPAH-907__20260808T064304Z.jsonl
---
author: oompah
created: 2026-08-08 06:44
---
Retrying (attempt #3, agent: deep)
---
author: oompah
created: 2026-08-08 06:44
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-08 06:44
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 80s (attempt #4)
---
author: oompah
created: 2026-08-08 06:44
---
Run #4 [attempt=4, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 36s
- Log: OOMPAH-907__20260808T064437Z.jsonl
---
author: oompah
created: 2026-08-08 06:46
---
Retrying (attempt #4, agent: deep)
---
author: oompah
created: 2026-08-08 06:46
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-08 06:47
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 160s (attempt #5)
---
author: oompah
created: 2026-08-08 06:47
---
Run #5 [attempt=5, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 44s
- Log: OOMPAH-907__20260808T064651Z.jsonl
---
author: oompah
created: 2026-08-08 06:50
---
Retrying (attempt #5, agent: deep)
---
author: oompah
created: 2026-08-08 06:50
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-08 06:50
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 300s (attempt #6)
---
author: oompah
created: 2026-08-08 06:50
---
Run #6 [attempt=6, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 35s
- Log: OOMPAH-907__20260808T065036Z.jsonl
---
author: oompah
created: 2026-08-08 06:56
---
Retrying (attempt #6, agent: deep)
---
author: oompah
created: 2026-08-08 06:56
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-08 06:56
---
Run #7 [attempt=7, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 46s
- Log: OOMPAH-907__20260808T065626Z.jsonl
---
author: oompah
created: 2026-08-08 06:56
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 300s (attempt #7)
---
author: oompah
created: 2026-08-08 07:02
---
Retrying (attempt #7, agent: deep)
---
author: oompah
created: 2026-08-08 07:02
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-08 07:02
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 300s (attempt #8)
---
author: oompah
created: 2026-08-08 07:02
---
Run #8 [attempt=8, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 46s
- Log: OOMPAH-907__20260808T070230Z.jsonl
---
author: oompah
created: 2026-08-08 07:08
---
Retrying (attempt #8, agent: deep)
---
author: oompah
created: 2026-08-08 07:08
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-08 07:08
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 300s (attempt #9)
---
author: oompah
created: 2026-08-08 07:08
---
Run #9 [attempt=9, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 36s
- Log: OOMPAH-907__20260808T070830Z.jsonl
---
author: oompah
created: 2026-08-08 07:14
---
Retrying (attempt #9, agent: deep)
---
author: oompah
created: 2026-08-08 07:14
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-08 07:14
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 300s (attempt #10)
---
author: oompah
created: 2026-08-08 07:14
---
Run #10 [attempt=10, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 34s
- Log: OOMPAH-907__20260808T071411Z.jsonl
---
author: oompah
created: 2026-08-08 07:19
---
Retrying (attempt #10, agent: deep)
---
author: oompah
created: 2026-08-08 07:20
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-08 07:20
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 300s (attempt #11)
---
author: oompah
created: 2026-08-08 07:20
---
Run #11 [attempt=11, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 55s
- Log: OOMPAH-907__20260808T072023Z.jsonl
---
author: oompah
created: 2026-08-08 07:39
---
Direct repair checkpoint: orphan recovery and epic rollup now share exact parent+child generation CAS under task locks, with owner/scheduler fences and fail-closed child reads. The repair is integrated in systemic head 6cbbd6ef7bb7882257c4c9e9175bd5b3edc14183; 97 focused tests and the 1076-test combined affected gate passed. The exact full make test gate is currently running clean before publication/terminalization.
---
author: oompah
created: 2026-08-09 05:10
---
Direct project-owner completion verified on composed rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e: exact full gate passed (18,874 passed, 7 skipped, 2 xfailed), all four durable workflow domains are live in enforce mode, no actionable global alerts remain, and current durable exhaustion/expired leases are zero.
---
<!-- COMMENTS:END -->
