---
id: OOMPAH-758
type: bug
status: In Progress
priority: 1
title: Atomically fence direct epic maintenance from ordinary integration enqueue
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:13:06.220562Z'
updated_at: '2026-08-04T11:17:55.804436Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3a5cf97524206a21bd89f17e45fdeef379b3dbd1ac80288a363273f3e8bf57a8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T11:15:15.825355+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed the supplied peer corpus. Closest tasks were\
    \ OOMPAH-163, OOMPAH-165, and OOMPAH-168, but all are terminal and address different\
    \ epic workflow issues. No active duplicate was confirmed.\nFocus handoff: duplicate_detector\
    \  \nDuplicate preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence:\
    \ Reviewed the supplied peer corpus. Closest tasks were OOMPAH-163, OOMPAH-165,\
    \ and OOMPAH-168, but all are terminal and address different epic workflow issues.\
    \ No active duplicate was confirmed."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9e50e5e6-b5b5-4665-8235-16bd48c13447
oompah.task_costs:
  total_input_tokens: 46601
  total_output_tokens: 240
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46601
      output_tokens: 240
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46601
    output_tokens: 240
    cost_usd: 0.0
    recorded_at: '2026-08-04T11:15:15.823679+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-758__20260804T111458Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-758
    source_sha: 5368e23617a98569caf7370b0f2eb63d41c8ba6b
    completed_at: '2026-08-04T11:15:15.842179+00:00'
---
## Summary

Triggered by: OOMPAH-755

Live regression of merged OOMPAH-731 on revision 5368e236. OOMPAH-755 is a direct maintenance helper identified by title 'Rebase epic-OOMPAH-740 onto main' plus parent OOMPAH-740. Its resolver correctly used the canonical shared epic worktree, advanced origin/epic-OOMPAH-740 from 583fb236 to proven head 5368e236, verified current-main/OOMPAH-735 ancestry, and submitted through the direct Done-only path; the task reached In Validation at 11:10 UTC. Nevertheless, a durable ordinary integration row was also created at 11:08:47 with task_branch=epic-OOMPAH-740, base_sha=583fb236, head_sha=5368e236. A later queue pass leased that stale row and failed integration preparation because git worktree add tried to check out epic-OOMPAH-740 while its authoritative registered worktree already owned the branch. The row became blocked, the task was reopened, and an actionable integration_retry alert appeared. This violates OOMPAH-731's no-enqueue/Done-only atomicity. Implementation scope: serialize task-handoff submission, worker-exit fallback, same-head/restart recovery, and direct-maintenance completion under one authority generation; once is_direct_epic_maintenance_issue is true, make ordinary queue enqueue impossible at every producer and atomically cancel any stale concurrent row before staging Done; fence late worker-exit and duplicate-screening paths after terminal ownership; reconcile already-published exact heads idempotently; clear integration retry/delivery alerts and cancel obsolete queue rows without touching the authoritative epic worktree. Relevant code: api_submit_issue/task-handoff submit, worker exit reconciliation, complete_direct_epic_maintenance_submission, integration_queue enqueue/claim, direct helper classification, terminal coordinator handoff, and restart recovery. Required tests: exact OOMPAH-755 race with direct submission and worker exit/concurrent tick; preexisting stale Ready/integrating/blocked row; restart between publish, queue write, and Done staging; duplicate submit; authoritative worktree already owns branch; lease loss; terminal override; ordinary child control. Acceptance criteria: a proven direct epic helper has exactly one Done-only lifecycle and zero ordinary integration rows; no queue executor attempts to create/reset its epic worktree; late/stale rows are cancelled before mutation and alerts clear; OOMPAH-755 converges without duplicate implementation; focused worker submission, integration queue/executor, maintenance, terminal lifecycle, alert, race, and restart tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 11:14
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 11:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 11:15
---
Task-specific recovery evidence: after duplicate screening finished and no OOMPAH-755 worker remained, the authenticated project-owner Done override was retried five times against the independently verified 5368e236 helper head. Every attempt returned HTTP 409 'The task changed before the override was requested' even though implementation/branch evidence was unchanged; the blocked ordinary queue row/refresh path keeps invalidating the fingerprint. No override committed. The fix must cancel/fence the obsolete row and compute current override evidence under the same ownership lock so OOMPAH-755 can converge without direct database/task-file edits.
---
author: oompah
created: 2026-08-04 11:15
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.6K in / 240 out [46.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 24s
- Log: OOMPAH-758__20260804T111458Z.jsonl
---
<!-- COMMENTS:END -->
