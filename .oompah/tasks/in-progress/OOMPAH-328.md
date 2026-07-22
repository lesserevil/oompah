---
id: OOMPAH-328
type: task
status: In Progress
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
assignee: null
created_at: '2026-07-21T20:34:42.051489Z'
updated_at: '2026-07-22T06:37:47.175429Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f75f746c-2a31-421f-bbf0-b352e555c097
oompah.task_costs:
  total_input_tokens: 25
  total_output_tokens: 6779
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 25
      output_tokens: 6779
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 25
    output_tokens: 6779
    cost_usd: 0.0
    recorded_at: '2026-07-22T06:37:35.739673+00:00'
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
<!-- COMMENTS:END -->
