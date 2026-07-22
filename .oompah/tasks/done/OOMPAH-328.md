---
id: OOMPAH-328
type: task
status: Done
priority: 2
title: Make project bootstrap and operator documentation forge-aware
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-323
- OOMPAH-325
- OOMPAH-327
labels:
- focus-complete:duplicate_detector
- 'focus-complete:'
- focus-complete:security
assignee: null
created_at: '2026-07-21T20:34:42.051489Z'
updated_at: '2026-07-22T07:51:44.127024Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: edb162b3-58cd-4f74-bf38-9877bd9bf9e7
oompah.task_costs:
  total_input_tokens: 2330505
  total_output_tokens: 19091
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 2330505
      output_tokens: 19091
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 25
    output_tokens: 6779
    cost_usd: 0.0
    recorded_at: '2026-07-22T06:37:35.739673+00:00'
  - profile: default
    model: unknown
    input_tokens: 731695
    output_tokens: 4512
    cost_usd: 0.0
    recorded_at: '2026-07-22T06:41:34.720509+00:00'
  - profile: standard
    model: unknown
    input_tokens: 445957
    output_tokens: 1944
    cost_usd: 0.0
    recorded_at: '2026-07-22T06:43:10.514479+00:00'
  - profile: deep
    model: unknown
    input_tokens: 369422
    output_tokens: 2153
    cost_usd: 0.0
    recorded_at: '2026-07-22T06:47:58.298403+00:00'
  - profile: default
    model: unknown
    input_tokens: 783406
    output_tokens: 3703
    cost_usd: 0.0
    recorded_at: '2026-07-22T07:10:01.305913+00:00'
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, Webhooks, UI, bootstrap, and operations.

Extend project-bootstrap, readiness checks, templates, and operator documentation for GitLab.com and GitLab 17+ self-managed projects. Validate token/API access, label creation, issue tracker access, MR access, pipeline read access, state-branch push access, public HTTPS webhook URL, hook creation, and polling fallback. Document minimum GitLab token scopes, direct public webhook deployment, ordinary auto-merge semantics, merge-train non-support, recovery procedures, and GitHub compatibility.

Tests:
- Bootstrap dry-run fixtures for success plus each capability failure.
- Documentation contract tests for required GitLab configuration and security guidance.
- Existing GitHub bootstrap/readiness tests remain green.

Acceptance criteria:
- An operator can bootstrap a GitLab project without undocumented manual steps.
- Failure output identifies the exact missing capability and remediation.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 06:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 06:34
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 06:35
---
Understanding: Investigating whether OOMPAH-328 ('Make project bootstrap and operator documentation forge-aware') is a duplicate of any existing task. The issue asks for GitLab-aware bootstrap, readiness checks, templates, and operator docs. Searching for similar tasks now.
---
author: oompah
created: 2026-07-22 06:37
---
Discovery: Duplicate investigation complete. OOMPAH-328 is NOT a duplicate.

**Search performed:**
- Searched .oompah/tasks/ for: bootstrap, gitlab, forge, forge-aware, forge-parity, operator doc, readiness check — across all task states (open, in-progress, backlog, done, merged, archived)
- Reviewed all 282 task files; no task references 'gitlab' anywhere
- Reviewed OOMPAH-258 (Merged): 'Configure Git state branches in project-bootstrap and operator documentation' — different scope (state branches for GitHub only, not GitLab forge support)
- Reviewed OOMPAH-281 (Open): 'Self-hosted GitHub Actions runner' — unrelated
- Reviewed OOMPAH-282 (Backlog): UnicodeEncodeError in state_branch_migration — unrelated
- Blockers OOMPAH-323, OOMPAH-325, OOMPAH-327 do not yet exist in .oompah/tasks/ (task counter only reaches OOMPAH-282)

**Evidence:**
- The gitlab-forge-parity.md plan exists in plans/ and describes the full scope; OOMPAH-328 is the first task targeting the bootstrap+docs section of that plan
- No prior task has implemented GitLab-aware bootstrap, readiness checks, token scope validation, webhook URL/hook creation, or operator docs for GitLab

**Closest task reviewed:**
- OOMPAH-258 (Merged): covered state-branch bootstrap and docs for GitHub projects. Distinct from OOMPAH-328 which specifically extends bootstrap for GitLab/forge awareness per plans/gitlab-forge-parity.md.
---
author: oompah
created: 2026-07-22 06:37
---
Focus handoff: duplicate_detector

1. **Outcome**: OOMPAH-328 is NOT a duplicate. No existing task covers GitLab forge-aware bootstrap or operator documentation. This is the first task targeting the 'Webhooks, UI, bootstrap, and operations' section of plans/gitlab-forge-parity.md for the bootstrap/docs portion.

2. **Relevant files, evidence, decisions**:
   - plans/gitlab-forge-parity.md §'Webhooks, UI, bootstrap, and operations' — the plan that scopes this task. Specifically: extend project-creation/bootstrap to validate GitLab token scopes, label creation, webhook URL, hook creation; document minimum token scopes, auto-merge semantics, polling fallback, recovery procedures.
   - oompah/project_bootstrap/__init__.py — existing bootstrap entry point (GitHub only currently)
   - docs/operator-runbook.md — existing operator docs to extend for GitLab
   - docs/managed-project-onboarding.md — existing onboarding docs to extend
   - Blocker tasks OOMPAH-323, OOMPAH-325, OOMPAH-327 are not yet in .oompah/tasks/ (tracker max is OOMPAH-282). These need to be created or will be auto-created by oompah.

3. **Remaining work**:
   - Extend project_bootstrap/ to detect forge=gitlab and validate: token API access, label create permission, issue tracker access, MR access, pipeline read, state-branch push, public HTTPS webhook URL, hook creation capability, polling fallback
   - Bootstrap dry-run fixtures for success and each failure scenario
   - Documentation: min GitLab token scopes, public webhook deployment, auto-merge semantics, merge-train non-support, recovery procedures, GitHub compatibility
   - Documentation contract tests
   - All existing GitHub bootstrap/readiness tests must stay green

4. **Recommended next focus**: feature (implementation of bootstrap validation + docs)
---
author: oompah
created: 2026-07-22 06:37
---
Agent completed successfully in 162s (6804 tokens)
---
author: oompah
created: 2026-07-22 06:37
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 51, Tool calls: 38
- Tokens: 25 in / 6.8K out [6.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 42s
- Log: OOMPAH-328__20260722T063456Z.jsonl
---
author: oompah
created: 2026-07-22 06:37
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 06:37
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 06:37
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-22 06:37
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-22 06:37
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 8s
- Log: OOMPAH-328__20260722T063747Z.jsonl
---
author: oompah
created: 2026-07-22 06:38
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 06:38
---
Agent completed successfully in 0s
---
author: oompah
created: 2026-07-22 06:38
---
Run #2 [attempt=2, profile=standard, role=— -> Claude/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: normal, Duration: 0s
---
author: oompah
created: 2026-07-22 06:38
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-22 06:38
---
Focus handoff from `` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 06:38
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 06:38
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-22 06:41
---
Agent completed successfully in 166s (736207 tokens)
---
author: oompah
created: 2026-07-22 06:41
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 11
- Tokens: 731.7K in / 4.5K out [736.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 46s
- Log: OOMPAH-328__20260722T063850Z.jsonl
---
author: oompah
created: 2026-07-22 06:41
---
Agent completed without closing this issue (166s (736207 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 06:41
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 06:41
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-22 06:43
---
Agent completed successfully in 78s (447901 tokens)
---
author: oompah
created: 2026-07-22 06:43
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 8
- Tokens: 446.0K in / 1.9K out [447.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 18s
- Log: OOMPAH-328__20260722T064153Z.jsonl
---
author: oompah
created: 2026-07-22 06:43
---
Agent completed without closing this issue (78s (447901 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-22 06:43
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-22 06:43
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-22 06:47
---
Run #3 [attempt=3, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 7
- Tokens: 369.4K in / 2.2K out [371.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 21s
- Log: OOMPAH-328__20260722T064338Z.jsonl
---
author: oompah
created: 2026-07-22 06:47
---
Agent completed successfully in 261s (371575 tokens)
---
author: oompah
created: 2026-07-22 06:48
---
Agent completed 3 times without closing this issue. Human action required: review the agent run history and task state, then either close the task if the work is done or add specific guidance and move it back to Open.
---
author: oompah
created: 2026-07-22 06:57
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #2)

**State audited:** `Needs Human`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Last agent comment signals completion without a human question; the Needs Human transition appears accidental.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-07-22 07:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 07:07
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-22 07:10
---
Agent completed successfully in 169s (787109 tokens)
---
author: oompah
created: 2026-07-22 07:10
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 12
- Tokens: 783.4K in / 3.7K out [787.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 49s
- Log: OOMPAH-328__20260722T070715Z.jsonl
---
author: oompah
created: 2026-07-22 07:10
---
Agent completed 4 times without closing this issue. Human action required: review the agent run history and task state, then either close the task if the work is done or add specific guidance and move it back to Open.
---
author: oompah
created: 2026-07-22 07:17
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #3)

**State audited:** `Needs Human`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Last agent comment signals completion without a human question; the Needs Human transition appears accidental.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-07-22 07:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 07:32
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-22 07:38
---
Understanding: Security Auditor reviewing OOMPAH-328 GitLab forge-aware bootstrap. Tests pass (11479). Prior agents didn't close because the actual GitLab bootstrap readiness check feature is still unimplemented. Plan: (1) Security review existing GitLab code for OWASP issues, (2) Implement GitLab bootstrap readiness checks with security best practices, (3) Add documentation, (4) Run tests, (5) Close. Key security areas: webhook token validation, forge_base_url SSRF, token scoping, secret storage.
---
author: oompah
created: 2026-07-22 07:39
---
Discovery: Security audit complete + implementation plan.

SECURITY ISSUES FOUND:
1. (Medium) GitLab webhook handler processes events for unmatched projects without authentication. When no registered project matches the webhook repo slug, `_handle_webhook_event(event, None)` is still called, emitting FORGE_WEBHOOK_RECEIVED events on the bus unauthenticated. The endpoint docstring says 'fail closed' but the unmatched-project path falls through. Fix: return 200 ignored for unmatched.

2. (Low) forge_base_url validated as HTTPS but no private-IP block. Mitigated by local-only API exposure.

IMPLEMENTATION NEEDED (no GitLab bootstrap readiness exists):
- oompah/project_bootstrap/gitlab_readiness.py: capability checks (token, labels, issues, MR, pipeline, state-branch push, webhook URL, hook creation, polling fallback)
- tests/test_gitlab_bootstrap_readiness.py: dry-run fixtures for success + each failure
- docs/project-bootstrap.md: GitLab section (min token scopes, webhook, auto-merge, merge-train non-support, recovery)
- tests/test_docs_gitlab_contract.py: documentation contract tests

ALL changes now being implemented.
---
author: oompah
created: 2026-07-22 07:51
---
Implementation: All changes committed and pushed (b74e505da).

SECURITY FIX (oompah/server.py):
- GitLab webhook endpoint now returns 200 ignored for unregistered repos instead of emitting FORGE_WEBHOOK_RECEIVED events without authentication. Previously, any caller knowing the webhook URL could trigger event-bus emissions for unmatched repos — now the endpoint is fully fail-closed.

NEW CODE (oompah/project_bootstrap/gitlab_readiness.py):
- check_gitlab_readiness(): validates api_access, label_create, issue_access, mr_access, pipeline_read, state_branch_push, webhook_url, hook_create, polling_fallback
- dry_run mode: avoids state-mutating calls (probe labels/hooks not created)
- Short-circuit on API failure; token never appears in error output
- MINIMUM_TOKEN_SCOPES constant documents 'api' as minimum

TESTS (69 new, all 11548 pass):
- test_gitlab_bootstrap_readiness.py: 47 tests covering all capabilities
- test_docs_gitlab_contract.py: 21 documentation contract tests  
- test_server_webhooks.py: security regression test for webhook fix

DOCS:
- docs/project-bootstrap.md: full GitLab section (token scopes, webhook HTTPS, auto-merge, merge-train non-support, state-branch push, dry-run, recovery, GitHub compat)
- docs/operator-runbook.md: GITLAB_TOKEN and OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL table
---
author: oompah
created: 2026-07-22 07:51
---
Verification: make test passed — 11548 passed, 36 skipped, 0 failures (up from 11479 before this change, adding 69 new tests). Branch pushed to origin/epic-OOMPAH-318 at b74e505da.
---
author: oompah
created: 2026-07-22 07:51
---
Added GitLab forge-aware bootstrap readiness checks (check_gitlab_readiness with 9 capability checks), fixed security issue in GitLab webhook handler (unmatched repos now return ignored instead of processing unauthenticated events), added 69 tests (all 11548 pass), and added operator documentation (GitLab token scopes, webhook HTTPS, auto-merge semantics, merge-train non-support, state-branch push, recovery procedures). All acceptance criteria met.
---
<!-- COMMENTS:END -->
