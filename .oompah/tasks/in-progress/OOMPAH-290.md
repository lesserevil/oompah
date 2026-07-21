---
id: OOMPAH-290
type: task
status: In Progress
priority: 1
title: Enforce server-side authority boundaries for agent actions influenced by external
  intake
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-287
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T14:51:56.727670Z'
updated_at: '2026-07-21T22:58:05.604472Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 586e6af3-002e-439f-a387-6f3fae896181
oompah.task_costs:
  total_input_tokens: 27
  total_output_tokens: 6739
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 27
      output_tokens: 6739
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 27
    output_tokens: 6739
    cost_usd: 0.0
    recorded_at: '2026-07-21T22:48:47.565881+00:00'
---
## Summary

Audit tool and API paths reachable by agents working on externally sourced tasks. Add centralized checks requiring trusted server-side state for status transitions, task creation/decomposition, source changes, provider/project configuration, credential access, Git pushes, GitHub comments/labels, and release delivery actions. Never authorize an action solely because external issue text requests it. Emit an auditable denial reason while preserving normal approved workflows.

Dependency: Add provenance metadata for external content entering Oompah.

Tests: integration tests using externally sourced tasks that request protected actions; assert denial without trusted approval and success through the approved path.

Acceptance criteria: external prompt injection cannot grant capabilities or bypass transition or authorization gates.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 22:26
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:26
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 22:38
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 22:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 22:48
---
Focus handoff: duplicate_detector

1. **Outcome:** No duplicate confirmed. OOMPAH-290 is a unique child task in the OOMPAH-285 epic (Defend Oompah agents against prompt injection from external content). No existing task in the tracker covers its scope.

2. **Evidence reviewed:**
   - Searched all .oompah/tasks/ states (archived ~223 files, merged ~55 files, done, backlog, needs-ci-fix, needs-rebase) for keywords: authority boundaries, server-side, authorization gate, status transition, credential access, git push, agent action, external intake, prompt injection, decomposition, release delivery. Zero matches to OOMPAH-290's scope.
   - OOMPAH-285 (epic, In Progress): Parent epic explicitly lists OOMPAH-290 as a required child with its own distinct scope (server-side authority boundaries). Children cover separate layers: OOMPAH-286 (threat model), OOMPAH-287 (provenance metadata), OOMPAH-288 (prompt rendering boundaries), OOMPAH-289 (triage hardening), OOMPAH-290 (server-side enforcement), OOMPAH-291 (regression suite).
   - OOMPAH-286 (Merged): Defines threat model in plans/prompt-injection-protection.md, specifically §7 'Server-Side Authoritative Controls' — the planning artifact for OOMPAH-290, not a duplicate.
   - OOMPAH-287 (Merged): Provenance dataclass/enums — data model layer, not server-side enforcement.
   - OOMPAH-288 (Done): SAFETY_INSTRUCTION in prompt rendering — rendering layer only.
   - OOMPAH-289 (In Progress): Focus triage/model-only decision hardening — model decision layer only.
   - plans/prompt-injection-protection.md §7 maps the server-side controls OOMPAH-290 must verify/extend: task state transitions (statuses.py/server.py), label mutation (server.py), git push targets (workspace.py/scm.py), worktree path guard (api_agent.py/acp_tools.py), shell-as-tool-name intercept (api_agent.py), attachment path validation (server.py), MIME allowlist (attachments.py), budget enforcement (orchestrator.py/api_agent.py).
   - No archived or merged task covers centralized server-side authority checks for the full set of protected actions described in OOMPAH-290.

3. **Remaining work / risks:**
   - Audit all tool and API paths reachable by agents working on externally sourced tasks (start from acp_tools.py, api_agent.py, server.py, orchestrator.py).
   - Add centralized checks requiring trusted server-side state for: status transitions, task creation/decomposition, source changes, provider/project config, credential access, git pushes, GitHub comments/labels, release delivery actions.
   - Implement auditable denial reason emission when unauthorized action is attempted (log + structured error response).
   - Preserve normal approved workflows through the same checks.
   - Write integration tests using externally sourced task context that requests each protected action; assert denial without trusted approval and success through approved paths.
   - Dependency OOMPAH-287 is now Merged — the provenance infrastructure is in place. OOMPAH-288 is Done. OOMPAH-289 is still In Progress but OOMPAH-290 can proceed as it operates on a different layer (server API, not model prompts).
   - Key risk: some server-side controls already exist (per §7 of the threat model) — implementation agent should audit what guards are already in place vs. what gaps need filling, to avoid duplication.
   - Key files: oompah/server.py, oompah/statuses.py, oompah/acp_tools.py, oompah/api_agent.py, oompah/workspace.py, oompah/scm.py, oompah/orchestrator.py, oompah/attachments.py; tests/ (new integration test module).

4. **Recommended next focus:** security (implement centralized server-side authority boundary checks across the action surfaces listed above and write integration tests as specified in the acceptance criteria).
---
author: oompah
created: 2026-07-21 22:48
---
Agent completed successfully in 596s (6766 tokens)
---
author: oompah
created: 2026-07-21 22:48
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 52, Tool calls: 41
- Tokens: 27 in / 6.7K out [6.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 56s
- Log: OOMPAH-290__20260721T223858Z.jsonl
---
author: oompah
created: 2026-07-21 22:48
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 22:57
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 22:57
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-21 22:58
---
Understanding: I will audit agent-reachable mutation and delivery paths for trust/provenance-based authorization, add centralized server-side denials with audit reasons where gaps exist, and verify protected actions remain available through approved paths.
---
<!-- COMMENTS:END -->
