---
id: OOMPAH-661
type: task
status: In Progress
priority: null
title: Cancel stale implementation retries when task authority changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T13:12:19.387161Z'
updated_at: '2026-07-31T14:30:04.864432Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 562b7ed72adf9027a7d9db34d9cd19fb86ef816ab27561e4814477ad1a341fc4
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T13:57:19.312354+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive duplicate investigation, I have searched across\
    \ the entire oompah task tracking system and found no existing active task that\
    \ covers the same ground as OOMPAH-661.\n\n## Investigation Summary\n\n**Search\
    \ scope:**\n- All `.oompah/tasks/` directories: open, merged, backlog, and archived\
    \ (200+ tasks)\n- Keywords searched: `retry`, `scheduler`, `dispatch`, `reconcil`,\
    \ `implementation`, `generation.*authority`, `submission.*status`, `head.*replacement`,\
    \ `restart.*persisted`, `stale`\n- Documentation: `docs/`, `plans/`, `README.md`,\
    \ `WORKFLOW.md`\n\n**Findings:**\n- **Active open tasks:** Only OOMPAH-281 (GitHub\
    \ Actions self-hosted runner) \u2014 unrelated\n- **Backlog tasks:** Only OOMPAH-282\
    \ (state_branch_migration error) \u2014 unrelated\n- **No tasks found** matching\
    \ OOMPAH-661's scope: delayed implementation retry cancellation, generation authority\
    \ binding, status-change driven retry invalidation, or worktree reconciliation\
    \ with stale retry cleanup\n- **Referenced case (OOMPAH-660):** Does not exist\
    \ in tracked tasks (may be GitHub issue or external reference)\n\n**Closest reviewed\
    \ candidates:** None match the implementation scope of binding retries to exact\
    \ generation states and canceling them on authority changes.\n\n---\n\n**Focus\
    \ handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:** Exhaustive search of all oompah native tasks\
    \ in open, backlog, and merged states yielded no existing task covering implementation\
    \ retry cancellation based on generation authority changes. OOMPAH-661 is addressing\
    \ a unique problem identified from the live OOMPAH-660 case: stale implementation\
    \ retries persisting after task resubmission, leading to redundant worker dispatch\
    \ and UI health issues. No existing task has this scope."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 0c78b242-c254-45ac-8933-17ee1f7d026a
oompah.task_costs:
  total_input_tokens: 154
  total_output_tokens: 3957
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 154
      output_tokens: 3957
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 154
    output_tokens: 3957
    cost_usd: 0.0
    recorded_at: '2026-07-31T13:57:19.310768+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-661__20260731T135529Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-661
    source_sha: 507534cf21032d8bd94ce6e9d5dcd4d1497b3a65
    completed_at: '2026-07-31T13:57:19.322808+00:00'
---
## Summary

Live reproduction on 2026-07-31: OOMPAH-660 failed implementation dispatch because its clean shared epic worktree had not yet followed a force-pushed rebase. The scheduler accumulated retry attempt #6 with the old divergence error. After the operator proved patch equivalence, reconciled the worktree, and successfully resubmitted OOMPAH-660 to Ready to Integrate, /api/v1/state still reported the stale implementation retry and counted the task as retrying while its exact head was already queued for integration. This is stale generation authority and can produce a redundant worker dispatch or misleading UI health.\n\nImplementation scope: bind every delayed implementation retry to the exact project/task/status/attempt/assignment/work-branch/head generation that failed; synchronously cancel and remove it when submission, status change, new assignment, head replacement, terminal transition, or operator reconciliation withdraws that generation; revalidate fresh tracker state and ownership immediately before any due retry dispatch; make cancellation idempotent across restart and ensure state/counts/alerts expose only actionable retries. Preserve historical run/error comments without treating them as live retry authority. Relevant code includes orchestrator retry scheduling/dispatch, task submission and status reconciliation, restart persistence, state serialization, and retry/watchdog tests.\n\nRequired deterministic tests: failed In Progress generation then submit same head to Ready clears retry immediately; Backlog/Open/Needs Human/terminal changes clear it; replacement head or attempt cannot inherit it; due-time race with submit allows only one authority winner; restart with stale persisted retry discards it; unrelated tasks/projects remain isolated; retrying UI count and error clear without deleting history. Acceptance: a retry can launch only while its exact failed implementation generation is still current, and OOMPAH-660-style reconciliation cannot leave a stale retry or spawn another worker after Ready to Integrate.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 13:55
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 13:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 13:57
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 42, Tool calls: 18
- Tokens: 154 in / 4.0K out [4.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 53s
- Log: OOMPAH-661__20260731T135529Z.jsonl
---
author: oompah
created: 2026-07-31 13:57
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 13:57
---
Focus: Event Api Redaction Specialist
---
author: oompah
created: 2026-07-31 14:29
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 153
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 32m 1s
- Log: OOMPAH-661__20260731T135749Z.jsonl
---
author: oompah
created: 2026-07-31 14:30
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-31 14:30
---
Focus: Event Api Redaction Specialist
---
<!-- COMMENTS:END -->
