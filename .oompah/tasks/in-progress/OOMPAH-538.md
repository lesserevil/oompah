---
id: OOMPAH-538
type: task
status: In Progress
priority: null
title: Make spawned-agent task handoffs authenticate without exposing service credentials
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T00:37:23.786577Z'
updated_at: '2026-07-29T00:41:38.435072Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ed30fc8ebb3f597f003d7302a72f5d668323d86c30d630f0aa9b7e03d24e0cec
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T00:40:19.225674+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Reviewed active OOMPAH-281 (self-hosted CI runner) and OOMPAH-282 (state-branch
    migration encoding failure); neither covers worker task-handoff authentication.
    Closest historical tasks are OOMPAH-6 (GitHub intake credentials) and OOMPAH-256
    (state-branch tracker writes), both terminal and materially distinct.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 5c6a838c-97c4-418f-8544-d41a32b8b8cb
oompah.task_costs:
  total_input_tokens: 338230
  total_output_tokens: 1640
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 338230
      output_tokens: 1640
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 338230
    output_tokens: 1640
    cost_usd: 0.0
    recorded_at: '2026-07-29T00:40:19.223661+00:00'
---
## Summary

Production follow-up from OOMPAH-469. A spawned Codex implementation worker completed, committed, and pushed commit 4ee93839f, then followed the project bootstrap instruction to run 'oompah task set-status OOMPAH-469 Done --project proj-14849f1b'. The command returned HTTP 401 Unauthorized because the worker session lacked usable task-service authentication. The task stayed Open and was redundantly dispatched again after restart until an operator repaired the handoff.\n\nImplementation scope:\n- Provide spawned agents a safe supported way to execute their authorized oompah task comments/status handoff. Prefer server-owned/session-scoped task tooling or narrowly scoped credentials; do not expose the operator's reusable HTTP password to untrusted task content or the repository.\n- Ensure generated prompts/bootstrap instructions select the working handoff path in ACP/API/subprocess provider modes.\n- Treat an implementation that pushed successfully but cannot update the tracker as an observable handoff failure that cannot silently look dispatchable.\n- Preserve authority-boundary checks and project scoping.\n\nRequired tests:\n- An authenticated spawned worker can comment and transition its own task through the documented command/tool path.\n- A worker cannot mutate another project/task outside its grant or read/reuse the operator credential.\n- Authentication failure is recorded and prevents immediate redundant redispatch of the completed commit.\n- Cover ACP Codex plus at least one other backend/session path and run make test.\n\nAcceptance criteria:\nA worker completing the AGENTS.md session checklist can update its assigned task without HTTP 401; no reusable service secret is exposed in prompts/logs/environment-readable repository files; failed handoffs are visible and do not cause duplicate implementation runs; project and action-policy authorization remains enforced.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 00:38
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-29 00:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 00:40
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 7
- Tokens: 338.2K in / 1.6K out [339.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 53s
- Log: OOMPAH-538__20260729T003829Z.jsonl
---
author: oompah
created: 2026-07-29 00:41
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 00:41
---
Focus: Security Auditor
---
<!-- COMMENTS:END -->
