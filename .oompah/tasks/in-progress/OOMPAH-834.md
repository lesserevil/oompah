---
id: OOMPAH-834
type: task
status: In Progress
priority: 1
title: Bind implementation lifecycle events to durable task-scoped handlers
parent: OOMPAH-804
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:38:27.595461Z'
updated_at: '2026-08-06T09:29:00.042840Z'
work_branch: epic-OOMPAH-804--task-OOMPAH-834
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a6f9dee590a1fc5a8c40f1239ab3ebaa8e29734260cd74804b838af5ad054eda
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T09:18:57.011462+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-804 is the parent production-runtime integration,\
    \ while OOMPAH-835, OOMPAH-836, and OOMPAH-837 cover separate review, integration,\
    \ and epic domains. None duplicates this task\u2019s nine implementation lifecycle\
    \ actions.\nFocus handoff: duplicate_detector  \nDuplicate preflight verdict:\
    \ no_duplicate  \nMatches: none  \n\nEvidence: OOMPAH-804 is the parent production-runtime\
    \ integration, while OOMPAH-835, OOMPAH-836, and OOMPAH-837 cover separate review,\
    \ integration, and epic domains. None duplicates this task\u2019s nine implementation\
    \ lifecycle actions."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9162ae12-e303-4e78-af51-0eeb40b04d8b
oompah.work_branch: epic-OOMPAH-804--task-OOMPAH-834
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-804--task-OOMPAH-834
  base_branch: epic-OOMPAH-768--task-OOMPAH-804
  base_sha: f89c477d4c03a8992a7278337182c0352da5de16
  updated_at: '2026-08-06T09:28:38.457695+00:00'
oompah.task_costs:
  total_input_tokens: 49361
  total_output_tokens: 271
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 49361
      output_tokens: 271
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 49361
    output_tokens: 271
    cost_usd: 0.0
    recorded_at: '2026-08-06T09:18:57.009999+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-834__20260806T091844Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-804--task-OOMPAH-834
    source_sha: 2a09b085bfb71b742c07d8ed91bc1c76add5d029
    completed_at: '2026-08-06T09:18:57.028464+00:00'
---
## Summary

Implement the production backend and event cutover for all nine ImplementationWorkflow actions: implementation_start, direct_owner_claim, duplicate_screening, focus_handoff, worker_exit, validation_submission, authority_revocation, implementation_retry, and implementation_recovery. Add a crash-safe exact disposition/effect-receipt ledger keyed by project, task, workflow generation, action, and immutable head/evidence; make inspect/apply/verify restart-idempotent and project-scoped. Route accepted API/ACP owner claims/releases, task handoffs/submissions, dispatch, worker exit, revocation, retry, duplicate screening, and startup recovery through schedule_event in enforce mode, disabling the corresponding legacy writer/timer/ownership path without calling whole-project sweeps from a task job. Relevant files: oompah/implementation_workflow.py, oompah/workflow_runtime.py or a new typed adapter module, oompah/orchestrator.py, oompah/server.py, workflow job/transition services. Required tests: native tracker plus temporary repo, exact multi-project routing, owner/submission races, child-exit crash after apply before verify, restart replay, stale generation fencing, retry timing, duplicate preflight, and enforce single-writer assertions. Acceptance: every implementation action has a real project-bound handler and production event source; durable job/receipt is the sole enforce-mode owner; no stale callback or legacy map can duplicate an effect.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 09:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 09:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 09:18
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 49.4K in / 271 out [49.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 42s
- Log: OOMPAH-834__20260806T091844Z.jsonl
---
author: oompah
created: 2026-08-06 09:19
---
Implementation lifecycle handlers are complete at exact head 2a09b085bfb71b742c07d8ed91bc1c76add5d029 and composed into the validated OOMPAH-804 parent head. Parent-level affected workflow validation passed 2397 tests; terminal mutation scan passed 8/8; secrets and critical Ruff checks passed.
---
author: oompah
created: 2026-08-06 09:28
---
The combined-tree quality gate failed on `epic-OOMPAH-804--task-OOMPAH-834`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
Combined-tree quality gate infrastructure_error: Quality gate owner metadata does not match the exact resolved candidate head.
```
---
author: oompah
created: 2026-08-06 09:28
---
Task-scoped OOMPAH-858 recovery: removed the already-satisfied OOMPAH-781 finish edge after verifying OOMPAH-781 is Done/audited and exact head 6a84d9bcc is reachable from validated parent composition f89c477d. This prevents the deployed nested-queue target resolver from misclassifying the completed cross-container prerequisite while preserving its implementation evidence.
---
author: oompah
created: 2026-08-06 09:28
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-06 09:28
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 09:29
---
Understanding: I will reconcile the exact-head quality-gate metadata failure, inspect the existing lifecycle-event implementation and its focused tests, then make the smallest durable fix, verify it, push, and resubmit.
---
<!-- COMMENTS:END -->
