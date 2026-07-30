---
id: OOMPAH-593
type: task
status: In Progress
priority: 1
title: Integrate and live-verify scoped Codex task CLI authentication
parent: OOMPAH-586
children: []
blocked_by: []
start_blocked_by: []
labels:
- focus-complete:docs
- needs:devops
assignee: null
created_at: '2026-07-30T14:14:54.281403Z'
updated_at: '2026-07-30T15:32:52.050430Z'
work_branch: epic-OOMPAH-586--task-OOMPAH-593
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7e0d6ed69f96dd5e289a4e8acbb2b5007bf599bb935b31f5a64158dcb9377c21
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T15:19:29.993817+00:00'
  matched_identifiers: []
  evidence: "Based on my thorough investigation, I have determined that **OOMPAH-593\
    \ is not a duplicate**.\n\n## Investigation Summary\n\nI searched comprehensively\
    \ across:\n- All `.oompah/tasks/` states (archived, merged, open, backlog) \u2014\
    \ 200+ tasks scanned\n- Search patterns: `Codex`, `live-verify`, `integration-auth`,\
    \ `least-privilege`, `scoped-credential`, `worker-launch`, `task-cli-auth`, `handoff-auth`,\
    \ `authentication`, `verification`\n- Documentation: `docs/` and `plans/` directories\n\
    - Project files: `README.md`, `WORKFLOW.md`\n\n**Key findings:**\n\n1. **OOMPAH-593\
    \ is explicitly an integration task** that depends on OOMPAH-575's implementation.\
    \ The description states: \"Use the existing OOMPAH-575 branch rather than reimplementing\
    \ it.\"\n\n2. **No existing tasks cover this scope.** There are no active/open\
    \ tasks that mention:\n   - Live verification of scoped authentication\n   - Codex\
    \ task CLI authentication\n   - Least-privilege probing\n   - Service-launched\
    \ worker verification\n\n3. **Unique acceptance criteria** distinguish OOMPAH-593\
    \ from any prior work:\n   - OOMPAH-575 reaches Merged (implementation prerequisite)\n\
    \   - A newly launched Codex worker completes documented task CLI workflow\n \
    \  - No operator credentials required\n   - No broader task authority\n   - Unrelated\
    \ tasks and expired capabilities fail closed\n\n4. **Task relationships are clear**:\
    \ OOMPAH-593 is part of epic OOMPAH-586 with coordination peers (OOMPAH-594, 595,\
    \ 597, 598), indicating this is a multi-task feature integration, not a duplicate.\n\
    \nThe only task with a related title in the system (OOMPAH-281) covers containerized\
    \ GitHub Actions runners, which is entirely unrelated.\n\n---\n\n**Focus handoff:\
    \ duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\n**Matches:\
    \ none**\n\n**Evidence:** Comprehensive search of 200+ existing tasks across all\
    \ states (archived, merged, open, backlog) found no existing tasks addressing\
    \ live verification of scoped Codex task CLI authentication. OOMPAH-593 is uniquely\
    \ positioned a"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 8faf098c-00f2-49a7-80eb-c1f672b5eea9
oompah.work_branch: epic-OOMPAH-586--task-OOMPAH-593
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-586--task-OOMPAH-593
  base_branch: epic-OOMPAH-586
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T15:21:38.098465+00:00'
oompah.task_costs:
  total_input_tokens: 75767
  total_output_tokens: 4950
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 130
      output_tokens: 4252
      cost_usd: 0.0
    sonnet:
      input_tokens: 75637
      output_tokens: 698
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 130
    output_tokens: 4252
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:19:29.991946+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 75637
    output_tokens: 698
    cost_usd: 0.0
    recorded_at: '2026-07-30T15:21:11.313684+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-593__20260730T150438Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-586--task-OOMPAH-593
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:19:29.999698+00:00'
  - run_id: OOMPAH-593__20260730T152040Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: docs
    source_branch: epic-OOMPAH-586--task-OOMPAH-593
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T15:21:11.318553+00:00'
---
## Summary

Triggered by: OOMPAH-575

Implementation scope

Use the existing OOMPAH-575 branch rather than reimplementing it. Get its focused handoff-auth regression through the normal delivery path, deploy it, then run a live least-privilege probe from a service-launched Codex task: view, comment, coordinate if allowed, and submit its assigned task; verify an unrelated task and expired/missing capability fail closed. Record only safe evidence. If the live path still returns 401, fix the actual launch/environment propagation gap with tests before resubmission.

Tests

Retain OOMPAH-575 focused suites, add any live-path reproducer required, and run make test for the final head.

Acceptance criteria

OOMPAH-575 reaches Merged; a newly launched Codex worker completes the documented task CLI workflow with no operator credentials and no broader task authority.
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
created: 2026-07-30 14:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 15:19
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 37, Tool calls: 15
- Tokens: 130 in / 4.3K out [4.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 19m 37s
- Log: OOMPAH-593__20260730T150438Z.jsonl
---
author: oompah
created: 2026-07-30 15:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 15:19
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-30 15:20
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-30 15:20
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 20s
- Log: OOMPAH-593__20260730T152001Z.jsonl
---
author: oompah
created: 2026-07-30 15:20
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-30 15:20
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-30 15:21
---
Agent completed successfully in 37s (76335 tokens)
---
author: oompah
created: 2026-07-30 15:21
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 1
- Tokens: 75.6K in / 698 out [76.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 37s
- Log: OOMPAH-593__20260730T152040Z.jsonl
---
author: oompah
created: 2026-07-30 15:21
---
Agent completed without closing this issue (37s (76335 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-30 15:21
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-30 15:21
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-30 15:25
---
Understanding: OOMPAH-593 must get the OOMPAH-575 regression suite through delivery, deploy, and live-probe a service-launched Codex worker to confirm scoped task-CLI auth. The underlying capability code is already live (OOMPAH-538, oompah/task_handoff.py, POST /api/v1/task-handoff, OOMPAH_TASK_HANDOFF_TOKEN + OOMPAH_TASK_HANDOFF_PROJECT_ID env plumbing in acp_backends/codex.py and acp_backends/opencode.py). OOMPAH-575 branch (origin/OOMPAH-575, single commit e404d6eb7) only adds regression tests (tests/test_acp_codex_backend.py::TestCodexHandoffAuth and tests/test_task_handoff.py::TestHandoffTokenFailClosed). This worktree currently has no delta over the epic-OOMPAH-586 base — the actual integration/probe/env-propagation work is devops+test, not documentation. As Technical Writer, my contribution is to publish the operator-facing scoped-task-CLI-authentication reference (env vars, endpoint, capability lifecycle, fail-closed behavior) and the live least-privilege probe procedure, then hand off to a devops/test specialist to run the actual integrate+probe path. Plan: (1) add docs/scoped-task-cli-authentication.md covering the shipped mechanism and probe procedure, (2) add a plans/ pointer in the existing focus-handoff-mutation-protocol doc if needed, (3) hand off with focus-complete:docs + needs:devops so the integration and live probe run under an operator.
---
author: oompah
created: 2026-07-30 15:30
---
Discovery: existing regression coverage on the current head (epic-OOMPAH-586) already includes TestTaskHandoffGrantStore, TestTaskCliHandoff, TestTaskScopeDirectPath, TestTaskHandoffEndpoint, TestAgentCredentialBoundary, and TestFailedHandoffLifecycle in tests/test_task_handoff.py — all pass locally (16 passed, 1 warning). OOMPAH-575 (single commit e404d6eb7 on origin/OOMPAH-575) layers on TestHandoffTokenFailClosed + TestCodexHandoffAuth for the explicit 401/403 matrix. No documentation existed for the OOMPAH_TASK_HANDOFF_TOKEN / OOMPAH_TASK_HANDOFF_PROJECT_ID / POST /api/v1/task-handoff mechanism; docs/authentication.md only covers operator HTTP Basic. That is the gap I can close as Technical Writer without touching code behavior.
---
author: oompah
created: 2026-07-30 15:31
---
Implementation (docs-only): Added docs/scoped-task-cli-authentication.md — an operator-facing reference for the shipped scoped task capability mechanism (env vars, endpoint, action allowlist, fail-closed matrix), plus a step-by-step live least-privilege probe procedure that captures only safe evidence (public identifiers, expected status codes) and never the opaque token or any operator credentials. Added an entry to docs/README.md and a cross-link from docs/authentication.md. All identifier and env var names verified against oompah/task_handoff.py, oompah/task_cli.py, oompah/server.py (POST /api/v1/task-handoff), oompah/orchestrator.py::_issue_task_handoff_token, and oompah/acp_backends/codex.py + opencode.py. No code behavior changes.
---
author: oompah
created: 2026-07-30 15:31
---
Verification: uv run pytest tests/test_task_handoff.py → 16 passed, 1 warning (the deprecation warning is unrelated to this doc). tests/test_acp_codex_backend.py has 0 handoff-named tests on the current head — expected; those land with OOMPAH-575. Doc claims cross-checked against source: TASK_HANDOFF_HEADER='x-oompah-task-capability', TASK_HANDOFF_TOKEN_ENV='OOMPAH_TASK_HANDOFF_TOKEN', TASK_HANDOFF_PROJECT_ENV='OOMPAH_TASK_HANDOFF_PROJECT_ID', endpoint path '/api/v1/task-handoff', allowed actions {view, comment, set-status, submit, add-label, remove-label, coordination-peers, coordination-inbox, coordination-send, coordination-checkpoint} — all consistent between orchestrator grant, endpoint allowlist, and CLI dispatch.
---
author: oompah
created: 2026-07-30 15:32
---
Focus handoff: docs

1. Outcome
Docs-only contribution shipped on branch epic-OOMPAH-586--task-OOMPAH-593 (commit fe52c187f). Added docs/scoped-task-cli-authentication.md as the operator-facing reference for the shipped scoped task capability mechanism, cross-linked from docs/authentication.md and indexed in docs/README.md. All identifier and endpoint semantics verified against source; tests/test_task_handoff.py runs 16/16 green on the current head. This closes the documentation half of the acceptance criteria ('documented task CLI workflow') and gives the operator running the live probe an unambiguous procedure and safe-evidence checklist.

2. Relevant files / commands / evidence
- docs/scoped-task-cli-authentication.md (new)
- docs/README.md (index entry)
- docs/authentication.md (See also cross-link)
- Verified against: oompah/task_handoff.py, oompah/task_cli.py, oompah/server.py (POST /api/v1/task-handoff at line 3247), oompah/orchestrator.py::_issue_task_handoff_token, oompah/acp_backends/codex.py (env injection at line ~775), oompah/acp_backends/opencode.py (env injection at line ~330), oompah/client_auth.py::agent_environment
- OOMPAH-575 tests live on origin/OOMPAH-575 (commit e404d6eb7): tests/test_acp_codex_backend.py::TestCodexHandoffAuth (5 cases), tests/test_task_handoff.py::TestHandoffTokenFailClosed (6 cases). Not merged yet.
- Focused suite: uv run pytest tests/test_task_handoff.py → 16 passed

3. Remaining work / risks
The acceptance criteria requires (a) OOMPAH-575 reaches Merged and (b) a newly launched Codex worker completes the documented workflow with no operator credentials. My docs-only work does not integrate OOMPAH-575 and does not perform the live probe. Remaining steps for the next focus:

a. Land OOMPAH-575: merge origin/OOMPAH-575 (fast-forward or normal submit path) so TestCodexHandoffAuth and TestHandoffTokenFailClosed run in CI on the epic branch. Because the tests are additive and cover behavior already implemented by OOMPAH-538, this is a low-risk integration.

b. Dispatch a Codex worker to a real task in a real project through the standard orchestrator path. Verify from the worker log that: (i) OOMPAH_TASK_HANDOFF_TOKEN was injected non-empty, (ii) 'oompah task view/comment/set-status/submit' on the assigned task succeed, (iii) 'oompah task view' against a different task in the same project rejects with 403 (server-side) or 'not granted' (CLI-side), (iv) after grant expiry (15 min default), any further operation returns 401. Record only the codes and identifiers per the probe procedure — never the token.

c. If step (b) yields a 401 on the worker's own task, DO NOT paper over it with operator credentials. The docs/scoped-task-cli-authentication.md 'Troubleshooting → 401' section names the two likely causes (subprocess env not receiving the token; orchestrator _issue_task_handoff_token returning None). Add a targeted regression to tests/test_task_handoff.py or tests/test_acp_codex_backend.py before shipping the fix.

Risk: the live probe requires operator access to a running service and the ability to launch a real worker. This is outside a docs specialist's scope.

4. Recommended next focus: devops (or test if the launch path is already exercised in a working test harness). The next agent needs operator-shell access to dispatch a worker and observe its log; the docs I shipped give them the exact fail-closed matrix to compare against.
---
author: oompah
created: 2026-07-30 15:32
---
Coordination note (post-handoff): OOMPAH-594 (epic-sibling) started implementation. My docs focus is already handed off (focus-complete:docs + needs:devops applied, commit fe52c187f pushed). No overlap with the new docs/scoped-task-cli-authentication.md — that file is task-CLI capability documentation, not part of any sibling task's changed-path set that I'm aware of. If OOMPAH-594's implementation touches oompah/task_handoff.py, oompah/task_cli.py, or the /api/v1/task-handoff endpoint, the incoming devops specialist should re-verify the doc's identifier and endpoint claims before running the live probe.
---
<!-- COMMENTS:END -->
