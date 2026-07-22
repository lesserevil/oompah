---
id: OOMPAH-398
type: task
status: In Progress
priority: 1
title: Add configurable stalled-task remediation watchdog
parent: null
children: []
blocked_by: []
labels:
- reliability
- watchdog
assignee: null
created_at: '2026-07-22T03:59:50.765371Z'
updated_at: '2026-07-22T04:01:38.197147Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3e3e0961-2158-4402-aa35-2380894daa7a
oompah.task_costs:
  total_input_tokens: 191477
  total_output_tokens: 1295
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 191477
      output_tokens: 1295
      cost_usd: 0.0
  runs:
  - profile: standard
    model: unknown
    input_tokens: 191477
    output_tokens: 1295
    cost_usd: 0.0
    recorded_at: '2026-07-22T04:01:19.313691+00:00'
---
## Summary

Implement a scheduler-owned watchdog that periodically audits stalled task states and resolves them when the evidence supports a safe automated action. The schedule must be configurable through OOMPAH_STALLED_TASK_WATCHDOG_INTERVAL_SECONDS, defaulting to 1800 seconds (30 minutes); configuration belongs in .env/.env.example, not WORKFLOW.md.\n\nScope:\n- Audit Needs Human, Needs CI Fix, Needs Rebase, Needs Answer, and any explicit Blocked/Stalled status across all managed projects.\n- Classify each task as actionable, genuinely human-blocked, obsolete, or insufficient-evidence.\n- Perform only safe, evidence-backed remediations: reopen a task whose prior focus completed without a human question; archive an obsolete alert whose referenced CI/PR has succeeded or been superseded; transition a task to the appropriate automated repair state when a known retry/remediation path applies.\n- Never auto-close/archive a task with unresolved current CI failure, a pending user question, or ambiguous external state.\n- Record the evidence, decision, and action in an oompah-authored task comment and structured watchdog telemetry.\n- Surface audit counts, last-run time, action count, and skipped/manual-review reasons in the API/dashboard maintenance snapshot.\n\nTests:\n- Unit tests for schedule/default/env parsing and every classification outcome.\n- Fake tracker/SCM tests for safe reopen, safe archive, and refusal when evidence is ambiguous or CI is still failing.\n- Integration test that the watchdog is coalesced, respects its configured interval, and does not block normal dispatch.\n- Run make test.\n\nAcceptance criteria:\n- Default schedule is 30 minutes and can be changed only with the documented environment setting.\n- Every stalled state is evaluated without creating duplicate actions across repeated runs.\n- Automated changes are explainable from task comments and API telemetry.\n- Genuine human blockers remain untouched and visible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 04:00
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 04:00
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-22 04:01
---
Agent completed successfully in 43s (192772 tokens)
---
author: oompah
created: 2026-07-22 04:01
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 191.5K in / 1.3K out [192.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 43s
- Log: OOMPAH-398__20260722T040039Z.jsonl
---
author: oompah
created: 2026-07-22 04:01
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-398`. Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
<!-- COMMENTS:END -->
