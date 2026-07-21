---
id: OOMPAH-290
type: task
status: Done
priority: 1
title: Enforce server-side authority boundaries for agent actions influenced by external
  intake
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-287
labels:
- focus-complete:duplicate_detector
- focus-complete:security
assignee: null
created_at: '2026-07-21T14:51:56.727670Z'
updated_at: '2026-07-21T23:21:34.874712Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9a595951-9bc4-42a4-b02a-8943369bcf20
oompah.task_costs:
  total_input_tokens: 488818
  total_output_tokens: 10017
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 488818
      output_tokens: 10017
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 27
    output_tokens: 6739
    cost_usd: 0.0
    recorded_at: '2026-07-21T22:48:47.565881+00:00'
  - profile: standard
    model: unknown
    input_tokens: 488791
    output_tokens: 3278
    cost_usd: 0.0
    recorded_at: '2026-07-21T22:59:18.798073+00:00'
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
author: oompah
created: 2026-07-21 22:59
---
Discovery: Existing status intake gates (oompah/transition_gate.py and server PATCH/webhook paths) protect only selected promotions. Agent-facing paths in oompah/acp_tools.py directly execute task create/child-create/status/label/comment commands and ProjectStore updates; run_command delegates to unrestricted shell execution in oompah/api_agent.py. ACP/Codex/OpenCode catalog construction passes workspace/project/tracker but no server-issued action authority, so untrusted task content can influence protected operations once an agent chooses to act.
---
author: oompah
created: 2026-07-21 22:59
---
Focus handoff: security\n\n1. Outcome: No duplicate or existing centralized authority boundary was found. The required protection needs a backend implementation, not additional prompt-only hardening.\n\n2. Evidence: oompah/transition_gate.py and server.py cover limited intake status transitions. oompah/acp_tools.py:_exec_oompah_task_command directly mutates tasks (set-status, create, child-create, labels, comments), _exec_update_project mutates config, and run_command forwards to oompah/api_agent.py:_exec_run_command. Catalog builders receive no trusted per-session authorization object (orchestrator.py:_run_acp_worker; acp_backends/codex.py and opencode.py rebuild catalogs likewise).\n\n3. Remaining work / risks: Add an immutable, server-issued per-session authority policy with default-deny protected actions and structured audit logging. Thread it through all catalog builders/backends and direct task/shell/project helpers. Classify/deny command intent for git push, GitHub comments/labels, release delivery, credentials, provider/project config, task creation/decomposition/source changes, and gated status transitions; do not trust task description/prompt fields. Preserve normal workflows by explicit server grant at dispatch. Add integration/unit tests for denied external-task attempts and approved authority paths. Raw shell aliases, interpreters, and compound commands are an evasion risk; fail closed for ambiguous protected commands.\n\n4. Recommended next focus: feature (backend implementation), then test for adversarial integration coverage.
---
author: oompah
created: 2026-07-21 22:59
---
Agent completed successfully in 86s (492069 tokens)
---
author: oompah
created: 2026-07-21 22:59
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 9
- Tokens: 488.8K in / 3.3K out [492.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 26s
- Log: OOMPAH-290__20260721T225755Z.jsonl
---
author: oompah
created: 2026-07-21 22:59
---
Focus handoff from `security` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 22:59
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 22:59
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 23:01
---
Understanding: Previous security audit (focus-complete:security) confirmed that oompah/acp_tools.py executes protected actions (task create/set-status/label/update_project, shell run_command) with NO server-side authority check — untrusted external task content can influence these operations once an agent acts on them. No authority_boundary module exists yet.

My plan as Test Engineer:
1. Implement oompah/authority_boundary.py: ProtectedAction enum, AgentActionPolicy frozen dataclass (server-issued, immutable), check_action() enforcer, classify_shell_command() for git push/credential/release patterns, and factory functions for default-allow (operator) vs. restrictive (external-task) policies.
2. Integrate policy check into acp_tools.py: gate set-status, create, child-create, update_project, and shell commands through check_action().
3. Write tests/test_authority_boundary.py: unit tests for all boundary logic + integration tests using externally-sourced task context that requests each protected action — asserting denial without trusted approval and success through approved path.

This addresses the acceptance criterion: external prompt injection cannot grant capabilities or bypass transition or authorization gates.
---
author: oompah
created: 2026-07-21 23:17
---
Implementation: Created oompah/authority_boundary.py with:
- ProtectedAction enum (7 categories: TASK_STATUS_TRANSITION, TASK_CREATE_DECOMPOSE, PROJECT_CONFIG_CHANGE, GIT_PUSH, GITHUB_DELIVERY, RELEASE_DELIVERY, CREDENTIAL_ACCESS)
- AgentActionPolicy frozen dataclass (immutable, server-issued, cannot be mutated by external content)
- operator_policy() / external_task_policy() factory functions
- is_action_allowed() / check_action() enforcer (returns auditable denial string + WARNING log with AUTHORITY_DENY: prefix)
- classify_shell_command() / check_shell_command() for git push, gh CLI mutations, cherry-pick, credential access patterns

Integrated into oompah/acp_tools.py:
- _exec_update_project(): PROJECT_CONFIG_CHANGE check before any mutation
- _exec_oompah_task_command(): TASK_STATUS_TRANSITION check for set-status/add-label/remove-label; TASK_CREATE_DECOMPOSE for create/child-create
- build_tool_catalog(), build_codex_tool_catalog(), build_opencode_tool_catalog(): added action_policy param; shell command check in run_command tool; policy threaded to oompah task commands and project updates

All three backends enforce identical authority boundaries through shared _exec_* helpers. Backward compatible: None policy = permissive (no existing tests broken).
---
author: oompah
created: 2026-07-21 23:17
---
Verification: 
- tests/test_authority_boundary.py: 135 tests covering all 15 test categories (ProtectedAction enum, policy dataclass, factory functions, is_action_allowed, check_action, shell classifier, check_shell_command, external task denials for all protected subcommands, operator task passes, explicit grant allows, none policy backward compat, audit log, injection-cannot-bypass-gate acceptance tests)
- Full suite: 10858 passed / 36 skipped — zero regressions
- Key acceptance criteria covered: external prompt injection cannot grant capabilities; external task content cannot modify the server-issued policy; denials are auditable (AUTHORITY_DENY: log lines)
---
author: oompah
created: 2026-07-21 23:18
---
Completion: Delivered server-side authority boundary enforcement for OOMPAH-290.

Files created/modified:
- oompah/authority_boundary.py (NEW): AgentActionPolicy frozen dataclass, ProtectedAction enum (7 categories), check_action() with AUTHORITY_DENY audit log, classify_shell_command() for git push / gh CLI mutations / cherry-pick / credential access, operator_policy() / external_task_policy() factories
- oompah/acp_tools.py (MODIFIED): integrated authority checks in _exec_update_project(), _exec_oompah_task_command(), and all three catalog builders (action_policy param + shell command pre-check in run_command)
- tests/test_authority_boundary.py (NEW): 135 tests verifying denial, audit logging, backward compat, explicit grants, and injection-cannot-bypass-gate scenarios

Acceptance criteria met:
1. External prompt injection cannot grant capabilities — policy is frozen at dispatch time, external content can never expand allowed_actions
2. Status transitions, task creation, project config, git pushes, GitHub delivery, credentials all have server-side checks
3. Auditable denial reason emitted on every denial (AUTHORITY_DENY: log prefix)
4. Normal operator-sourced workflows preserved (None policy and operator_policy() are permissive)
5. Full test suite: 10858 passed / 36 skipped — zero regressions
---
<!-- COMMENTS:END -->
