---
id: OOMPAH-476
type: feature
status: In Progress
priority: 1
title: Stage API, dashboard, and CLI terminal requests through the coordinator
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-467
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:24.379848Z'
updated_at: '2026-07-29T17:42:40.492163Z'
work_branch: epic-OOMPAH-459
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c5c4c9017c067d482a761e3a22a758d55e00a5cc1d2d4b3fe50959e2d4a650ec
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:28:33.369028+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation of the oompah task tracker, I\
    \ have searched for duplicate issues related to OOMPAH-476.\n\n## Search Strategy\n\
    \nI searched across `.oompah/tasks` (all states: open, backlog, merged, archived)\
    \ using the following keywords from OOMPAH-476's description:\n\n1. **Direct technical\
    \ terms**: `TerminalTransitionCoordinator`, `request_transition`, `override_reason`,\
    \ `audit_override`, `In Validation`, `stage.*validation`\n2. **API patterns**:\
    \ `PATCH.*status`, `set.*status`, `status.*endpoint`, `/api.*status`\n3. **Component\
    \ patterns**: `MCP.*tool`, `ACP.*tool`, `mutation.*tool`\n4. **Feature patterns**:\
    \ `Stage.*API`, `dashboard.*status`, `CLI.*terminal`, `coordinator.*request`\n\
    5. **Blocking dependencies**: Searched for OOMPAH-467, OOMPAH-475, OOMPAH-458\
    \ (all blocking this issue)\n\n## Results\n\nAll searches returned **no matches**.\
    \ The only active/backlog tasks in the system are:\n\n- **OOMPAH-281** (Open):\
    \ Self-hosted GitHub Actions runner setup \u2014 unrelated to status API coordination\n\
    - **OOMPAH-282** (Backlog): Unicode encoding error in state branch migration \u2014\
    \ unrelated to status APIs\n\nNo archived or merged tasks address:\n- Terminal\
    \ status request staging through a coordinator\n- Explicit audit override or override_reason\
    \ authorization\n- \"In Validation\" validation-staging responses\n- TerminalTransitionCoordinator\
    \ integration\n- Terminal transition auditing with audit IDs\n\n## Conclusion\n\
    \nOOMPAH-476 describes a unique, first-of-its-kind feature for staging terminal\
    \ status requests (Done/Merged/Archived) through a TerminalTransitionCoordinator\
    \ with audit tracking and explicit owner override support. This work has no active\
    \ duplicate.\n\n---\n\n**Focus handoff: duplicate_detector**\n\n**Duplicate preflight\
    \ verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:** Comprehensive\
    \ search across all task states (open, backlog, archived, merged) using 15+ keyword\
    \ patterns found zero matching tasks. The two only active tasks (OOMPAH-281, OOMPAH-282)\
    \ are unrelated (G"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 50f2b6b9-802f-47f3-adc9-190e7578b234
oompah.work_branch: epic-OOMPAH-459
oompah.task_costs:
  total_input_tokens: 45911240
  total_output_tokens: 91017
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 44553248
      output_tokens: 80374
      cost_usd: 0.0
    sonnet:
      input_tokens: 1357992
      output_tokens: 10643
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 114
    output_tokens: 4589
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:28:33.368354+00:00'
  - profile: default
    model: haiku
    input_tokens: 44553134
    output_tokens: 75785
    cost_usd: 0.0
    recorded_at: '2026-07-29T17:37:26.902212+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 1357992
    output_tokens: 10643
    cost_usd: 0.0
    recorded_at: '2026-07-29T17:41:59.827869+00:00'
---
## Summary

Implementation scope

Update the project-aware task PATCH/status endpoints, MCP/ACP task mutation tools, and oompah task set-status client so requests for Done, Merged, or Archived call TerminalTransitionCoordinator.request_transition. Return a response showing In Validation, requested target, and audit ID. Add explicit audit_override plus required override_reason inputs; authorize them through the coordinator owner check. Nonterminal transitions keep current behavior. Direct forge label mutations cannot express an override and must stage validation or be reverted by reconciliation. Update CLI help and errors without exposing metadata internals.

Tests

Cover each terminal target, nonterminal status, owner override, unauthorized/blank override, matching aliases, project resolution, MCP/ACP tool calls, CLI request/response, tracker errors, and backward-compatible clients that send only status. Run focused API/CLI tests and make test.

Acceptance criteria

All user- and agent-facing status interfaces stage terminal audits consistently, explicit owner overrides work, and no ordinary client can write a terminal status directly.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:26
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:26
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:28
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 41, Tool calls: 25
- Tokens: 114 in / 4.6K out [4.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 7s
- Log: OOMPAH-476__20260729T012631Z.jsonl
---
author: oompah
created: 2026-07-29 16:53
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 16:53
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 17:37
---
Agent completed successfully in 2635s (44628919 tokens)
---
author: oompah
created: 2026-07-29 17:37
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 185
- Tokens: 44.6M in / 75.8K out [44.6M total]
- Cost: $0.0000
- Exit: normal, Duration: 43m 55s
- Log: OOMPAH-476__20260729T165333Z.jsonl
---
author: oompah
created: 2026-07-29 17:37
---
Agent completed without closing this issue (2635s (44628919 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-29 17:37
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 17:37
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 17:42
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 69
- Tokens: 1.4M in / 10.6K out [1.4M total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 13s
- Log: OOMPAH-476__20260729T173748Z.jsonl
---
author: oompah
created: 2026-07-29 17:42
---
Agent completed successfully in 253s (1368635 tokens)
---
author: oompah
created: 2026-07-29 17:42
---
Agent completed without closing this issue (253s (1368635 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-29 17:42
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-29 17:42
---
Focus: Frontend Developer
---
<!-- COMMENTS:END -->
