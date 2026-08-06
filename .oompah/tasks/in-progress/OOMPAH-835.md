---
id: OOMPAH-835
type: task
status: In Progress
priority: 1
title: Bind review and CI actions to fresh project-scoped workflow handlers
parent: OOMPAH-804
children: []
blocked_by:
- OOMPAH-781
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:38:33.085889Z'
updated_at: '2026-08-06T00:06:02.649513Z'
work_branch: epic-OOMPAH-804--task-OOMPAH-835
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 22cf4c368761061373a8189b48d42124efc777fc8f7db0248c5530fde45b0728
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T00:03:48.231160+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** OOMPAH-835 is a distinct, domain-specific task explicitly\
    \ decomposed from parent epic OOMPAH-804. The parent's own comments (2026-08-05\
    \ 16:40) confirm the accepted scope structure: \"OOMPAH-804 now has finish-order\
    \ dependencies on all four [domain tasks including] OOMPAH-835 (review/CI handlers).\"\
    \ OOMPAH-834, OOMPAH-836, and OOMPAH-837 are parallel sibling implementations\
    \ for non-review domains (implementation, integration, epic), not duplicates.\
    \ All are active, non-terminal tasks with distinct scopes. Archived historical\
    \ tasks (OOMPAH-11 through OOMPAH-195) are in terminal states and historical context\
    \ only.\n# Duplicate Screening: OOMPAH-835\n\nI'll analyze the supplied task corpus\
    \ to determine if OOMPAH-835 is a duplicate of any active task.\n\n## Analysis\n\
    \n**OOMPAH-835 Scope:**\n- Implement production ReviewWorkflow backends for all\
    \ ten review/CI actions\n- Fresh provider-backed review fact source before enforce\
    \ reconciliation\n- TaskTransitionService intents instead of direct tracker writes\n\
    - Multi-project routing and shadow zero-write/enforce single-writer behavior\n\
    \n**Related Active Tasks in Corpus:**\n\n1. **OOMPAH-804** (In Progress) \u2014\
    \ Parent epic \"Wire durable workflow domains into the production runtime\"\n\
    \   - Coordinates all domain adapter integration\n   - Explicitly decomposes scope\
    \ into four sibling tasks:\n     - OOMPAH-834 (implementation handlers)\n    \
    \ - **OOMPAH-835 (review/CI handlers)** \u2190 current task\n     - OOMPAH-836\
    \ (integration handlers)\n     - OOMPAH-837 (epic handlers)\n\n2. **OOMPAH-834**\
    \ (In Progress) \u2014 \"Bind implementation lifecycle events to durable task-scoped\
    \ handlers\"\n   - Focused on implementation workflow (9 actions)\n   - Different\
    \ domain from review/CI\n\n3. **OOMPAH-836** (In Progress) \u2014 \"Bind integration\
    \ delivery and recovery to exact durable handlers\"\n   - Focused on integration\
    \ workflow (7 actions)\n   - Different domain from review/CI\n\n4. **OOMPAH-837**\
    \ (In Progress) \u2014 \"Bind epic rollup, delivery, repair, and cleanup to durable\
    \ handlers\"\n   - Focused on epic workflow (10 actions)\n   - Different domain\
    \ from review/CI\n\n5. **OOMPAH-781** (In Progress) \u2014 \"Cut terminal-audit\
    \ lifecycle over to durable decisions and jobs\"\n   - Focused on terminal-audit\
    \ workflow\n   - Different domain from review/CI\n\n## Verdict\n\n---\n\n**Focus\
    \ handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:** OOMPAH-835 is a distinct, domain-specific\
    \ task explicitly decomposed from parent epic OOMPAH-804. The parent's own comments\
    \ (2026-08-05 16:40) confirm the accepted scope structure: \"OOMPAH-804 now has\
    \ finish-order dependencies"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d4dc44e7-66e6-448e-92bc-650c72b410b5
oompah.work_branch: epic-OOMPAH-804--task-OOMPAH-835
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-804--task-OOMPAH-835
  base_branch: epic-OOMPAH-768--task-OOMPAH-804
  base_sha: b98ebb40d269ebeb7a134dc43add36bf782d9402
  updated_at: '2026-08-06T00:05:29.240933+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1808
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1808
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1808
    cost_usd: 0.0
    recorded_at: '2026-08-06T00:03:48.227202+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-835__20260806T000303Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-804--task-OOMPAH-835
    source_sha: 0baeb01f1a1ca4d2b75fd46807d2889ef83a9adf
    completed_at: '2026-08-06T00:03:48.252494+00:00'
---
## Summary

Implement production ReviewWorkflow backends for all ten actions: monitor, refresh, landing refresh, CI repair, conflict repair, terminal stage, closed repair, head reconciliation, merge, and capacity recheck. Provide a fresh provider-backed review fact source before enforce reconciliation (the current _reviews_cache is stale because runtime runs before legacy review refresh), extract exact task/review bodies from legacy project sweeps, and emit TaskTransitionService intents instead of direct tracker status writes. Keep forge mutations, review metadata, landing evidence, and capacity receipts fenced to exact project/task/review/head generations. Relevant files: oompah/review_workflow.py, oompah/workflow_runtime.py or a typed adapter module, orchestrator review refresh/reconciliation and forge helpers. Required tests: provider unavailable vs empty results, webhook/event ordering, CI/conflict/closed/head changes, merge idempotency, capacity release, restart after effect before verify, multi-project routing, and shadow zero-write/enforce single-writer behavior. Acceptance: every review action has truthful fresh evidence and a real handler; no task job invokes a whole-project sweep; UI reasons and executor decisions share the same durable receipt/transition.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 00:01
---
All prerequisite domain adapters are now available in prepared branches and the project has resumed. Promoting the review and CI production adapter so the oompah server can implement it in parallel while OOMPAH-791 and OOMPAH-796 advance through their parent rebases.
---
author: oompah
created: 2026-08-06 00:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 00:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 00:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.8K out [1.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 16s
- Log: OOMPAH-835__20260806T000303Z.jsonl
---
author: oompah
created: 2026-08-06 00:05
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 00:05
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 00:06
---
Understanding: Implementing production ReviewWorkflow backends for 10 actions with fresh provider-backed review facts, TaskTransitionService intents, and comprehensive isolation. Key files: review_workflow.py, workflow_runtime.py. Tests needed: provider availability, event ordering, CI/conflict/closed/head changes, merge idempotency, capacity release, multi-project routing. Starting codebase exploration.
---
<!-- COMMENTS:END -->
