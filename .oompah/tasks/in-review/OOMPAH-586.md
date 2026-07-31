---
id: OOMPAH-586
type: epic
status: In Review
priority: 0
title: Restore least-privilege task and lifecycle access
parent: OOMPAH-584
children:
- OOMPAH-593
- OOMPAH-594
- OOMPAH-595
blocked_by: []
start_blocked_by: []
labels:
- epic:rebasing
assignee: null
created_at: '2026-07-30T14:13:33.901470Z'
updated_at: '2026-07-31T00:36:17.752111Z'
work_branch: epic-OOMPAH-586
target_branch: epic-OOMPAH-584
review_url: https://github.com/lesserevil/oompah/pull/597
review_number: '597'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/597
oompah.review_number: '597'
oompah.work_branch: epic-OOMPAH-586
oompah.target_branch: epic-OOMPAH-584
oompah.agent_run_id: 1339ce75-a22a-456c-b7f0-5556f4c37888
oompah.task_costs:
  total_input_tokens: 245565
  total_output_tokens: 1879
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 245565
      output_tokens: 1879
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 245565
    output_tokens: 1879
    cost_usd: 0.0
    recorded_at: '2026-07-31T00:27:37.416571+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-586__20260731T002641Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: merge_conflict
    source_branch: epic-OOMPAH-586
    source_sha: ca49d0c25b30d149cb59f0af0bac57276c1f8120
    completed_at: '2026-07-31T00:27:37.421183+00:00'
---
## Summary

Goal

Restore reliable operator and service-launched worker access to the oompah task API without distributing server-wide credentials to agents. Integrate the existing OOMPAH-575 scoped-auth work, cover credential reload/drift, and make lifecycle health failures actionable.

Relevant context

Plain task CLI calls from repair workers returned HTTP 401. The running server also retained stale Basic-auth state until recycled even though the current on-disk htpasswd and client password matched. OOMPAH-575 already implements scoped Codex handoff regression coverage and must be reused rather than duplicated.

Acceptance criteria

Assigned workers can view/comment/submit only their task; unrelated or expired capabilities fail closed; operator status/restart/task commands survive supported credential rotation or report a precise actionable fault; secrets are never exposed to workers/logs; focused and complete Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-31 00:25
---
Branch quality gate passed for `ca49d0c25b30d149cb59f0af0bac57276c1f8120` using `make test` in 260.9s. Review creation may proceed.
---
author: oompah
created: 2026-07-31 00:26
---
YOLO: Merge conflict detected on MR #597. Rebase `epic-OOMPAH-586` onto epic-OOMPAH-584 and resolve conflicts.
---
author: oompah
created: 2026-07-31 00:26
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-31 00:26
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-07-31 00:27
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 5
- Tokens: 245.6K in / 1.9K out [247.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 59s
- Log: OOMPAH-586__20260731T002641Z.jsonl
---
author: oompah
created: 2026-07-31 00:27
---
Task handoff failed after the worker ran: the server-owned, task-scoped tracker capability could not update this task. The task is held in Needs Human and will not be redispatched automatically; verify the handoff service and reconcile the worker's branch before resuming it.
---
author: oompah
created: 2026-07-31 00:31
---
Operator takeover after the dispatched merge-conflict resolver completed but its task-scoped handoff failed. PR #597 remains DIRTY. I am rebasing exact remote epic head ca49d0c25 onto parent epic-OOMPAH-584 at c03e52f66 in an isolated worktree, preserving the managed worktree until the resolved head is verified and pushed with lease.
---
author: oompah
created: 2026-07-31 00:35
---
Resolved PR #597 directly after the server resolver's handoff failure. Rebased the six-child epic branch onto parent c03e52f66; Git correctly dropped patch-equivalent timeout commit 0a260f027 already present upstream. Conflict resolution preserves both terminal-audit health and operator/worker auth-health state, banners, and alerts. New exact head 04d072a5f was pushed with lease. Focused auth/dashboard/orchestrator/task-handoff suite: 423 passed; terminal mutation scan passed.
---
author: oompah
created: 2026-07-31 00:35
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-31 00:35
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-07-31 00:36
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 2
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 44s
- Log: OOMPAH-586__20260731T003536Z.jsonl
---
<!-- COMMENTS:END -->
