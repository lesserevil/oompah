---
id: OOMPAH-576
type: task
status: In Progress
priority: null
title: Reject integration submissions from the wrong checkout before mutating task
  worktrees
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T02:55:54.699694Z'
updated_at: '2026-07-30T13:37:46.557048Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3a0d0bdf76fa62b3007a3a55c9f010ba8c5e02c9d7ca4e709421b245ffd9f644
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T13:36:23.277930+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation, I have searched the entire tracker\
    \ for related tasks and found no active duplicate of OOMPAH-576.\n\n## Investigation\
    \ Summary\n\n**Searched locations:**\n- All open tasks (.oompah/tasks/open/):\
    \ OOMPAH-281, OOMPAH-282\n- All backlog tasks (.oompah/tasks/backlog/): OOMPAH-282\n\
    - All merged tasks (.oompah/tasks/merged/): OOMPAH-271, OOMPAH-272, OOMPAH-275,\
    \ OOMPAH-277, OOMPAH-278, OOMPAH-279, OOMPAH-280 (all are rebase operations for\
    \ epic-OOMPAH-253)\n- 300+ archived tasks: none matched\n- Design documents in\
    \ `plans/`: submit-queue.md (about GitHub Merge Queue and PR concurrency, different\
    \ scope), terminal-audit-enforcement.md (OOMPAH-483, about terminal state validation,\
    \ not submission validation)\n\n**Search queries used:**\n- `OOMPAH-483` (the\
    \ regression mentioned in the issue)\n- Keywords: `worktree`, `integration`, `submission`,\
    \ `queue`, `executor`, `submit`, `branch`\n- Patterns: `(submit.*worktree|integration.*worktree|task.*submission)`,\
    \ `(branch.*valid|branch.*check)`, `(reset.*worktree|mutation.*protect)`\n\n**Result:**\n\
    All matches found are in terminal states (Done, Merged, or Archived). The only\
    \ potentially related task is OOMPAH-483, which handles terminal-state audit enforcement\
    \ after tasks are marked Done \u2014 not submission validation before mutations.\n\
    \n**Conclusion:**\nOOMPAH-576 addresses a unique hardening requirement: rejecting\
    \ task submissions from the wrong checkout before mutating worktrees. No existing\
    \ open, in-progress, or active task covers this scope.\n\n---\n\n**Focus handoff:\
    \ duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\n**Matches:\
    \ none**\n\n**Evidence:** Comprehensive search of .oompah/tasks/ across all states\
    \ (open, backlog, merged, archived), plans/submit-queue.md, and terminal-audit-enforcement.md\
    \ returned no active tasks covering task submission checkout validation, integration\
    \ worktree protection, or prevention of destructive resets from wrong-checkout\
    \ submissions. OOMPAH-576 is a unique, first-of-"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 4332a750-942c-4bb5-8ebb-03e7753608fe
oompah.task_costs:
  total_input_tokens: 129304
  total_output_tokens: 6328
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 129304
      output_tokens: 6328
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 154
    output_tokens: 5287
    cost_usd: 0.0
    recorded_at: '2026-07-30T13:36:23.277495+00:00'
  - profile: default
    model: haiku
    input_tokens: 129150
    output_tokens: 1041
    cost_usd: 0.0
    recorded_at: '2026-07-30T13:37:23.091141+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-576__20260730T133433Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-576
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T13:36:23.281695+00:00'
  - run_id: OOMPAH-576__20260730T133636Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-576
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T13:37:23.095700+00:00'
---
## Summary

Implementation scope: harden task submission and integration worktree preparation so a submission made from the service/default-branch checkout cannot overwrite an existing task's recorded work branch or reset that task's live worktree to origin/main. Validate that the submitted local branch matches the task's expected work-branch namespace and pushed remote head before updating the queue; make integration worktree preparation fail closed when the queue branch disagrees with an already-registered worktree branch, without running reset. Relevant context/files: oompah/task_cli.py submit payload construction, server submit endpoint, oompah/integration_queue.py, oompah/integration_executor.py, and ProjectStore worktree preparation. Regression observed on OOMPAH-483: submitting from /home/shedwards/src/oompah queued task_branch=main, then the executor reset the registered epic-OOMPAH-459--task-OOMPAH-483 worktree from bc448cf08 to origin/main; the remote branch preserved the work and an operator restored it by fast-forward. Tests: cover wrong-checkout submit rejection, unchanged queue record, unchanged registered task worktree HEAD/branch, correct task-worktree resubmission, and no destructive reset on branch mismatch. Acceptance criteria: wrong-checkout submission returns an actionable error before tracker/queue/worktree mutation; correct submissions still integrate; a malformed/stale queue row cannot rewrite a registered worktree.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 13:34
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 13:34
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 13:36
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 61, Tool calls: 35
- Tokens: 154 in / 5.3K out [5.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 55s
- Log: OOMPAH-576__20260730T133433Z.jsonl
---
author: oompah
created: 2026-07-30 13:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 13:36
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-30 13:37
---
Agent completed successfully in 52s (130191 tokens)
---
author: oompah
created: 2026-07-30 13:37
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 3
- Tokens: 129.2K in / 1.0K out [130.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 52s
- Log: OOMPAH-576__20260730T133636Z.jsonl
---
author: oompah
created: 2026-07-30 13:37
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-576`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-30 13:37
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-30 13:37
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
