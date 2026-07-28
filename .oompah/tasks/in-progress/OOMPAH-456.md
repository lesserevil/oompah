---
id: OOMPAH-456
type: bug
status: In Progress
priority: 1
title: Make state-branch activation atomic and forge-aware for GitLab projects
parent: OOMPAH-451
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T12:36:06.205487Z'
updated_at: '2026-07-28T14:00:54.894107Z'
work_branch: epic-OOMPAH-451
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d4d597a1-1df0-4cbc-aef1-fa240970426c
oompah.work_branch: epic-OOMPAH-451
oompah.task_costs:
  total_input_tokens: 41
  total_output_tokens: 8727
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 41
      output_tokens: 8727
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 41
    output_tokens: 8727
    cost_usd: 0.0
    recorded_at: '2026-07-28T14:00:40.122348+00:00'
---
## Summary

Problem: nodevirt has state_branch_enabled=false and no local or remote oompah/state/proj-bbba976d branch. The Projects editor treats the setting as a plain PATCH boolean, so after the intake-alias bug is fixed it can enable reads before the branch exists. The supported migration preflight also runs git push --dry-run without the configured GitLab project token; it fails authentication and incorrectly tells the operator to verify GITHUB_TOKEN even though GitLab API readiness confirms access_level=40 and push permission.

Implementation scope: route UI activation through the validated state-branch bootstrap/migration workflow rather than a naked config flip; create and push the state branch, verify the remote commit and task layout, then atomically enable project state tracking. Use forge-aware noninteractive Git credentials derived safely from the project access token without embedding secrets in remote URLs, command output, persisted config, or logs. Make all validation and remediation messages forge-neutral. On failure, leave state_branch_enabled false and preserve both branches. Relevant files include oompah/templates/projects.html, oompah/server.py, oompah/state_branch_migration.py, oompah/projects.py, and migration/bootstrap tests.

Tests: reproduce a new GitLab native-Markdown project with only main, assert preflight and activation authenticate with the project token, verify the remote state branch before the config flips, cover auth and push failures with rollback/no partial enablement, and retain GitHub/native migration behavior; run make test.

Acceptance criteria: one supported action takes nodevirt from no state branch to a verified enabled state; a failed GitLab push cannot leave the project enabled; diagnostics mention the configured forge and never GitHub-specific credentials for GitLab.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 13:56
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 13:56
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 13:57
---
Understanding: Investigating OOMPAH-456 as Duplicate Investigator. The issue describes two bugs: (1) the Projects editor treats state_branch_enabled as a plain PATCH boolean and can enable reads before the branch exists; (2) the migration preflight runs git push --dry-run without the configured GitLab project token, fails auth, and incorrectly tells operator to verify GITHUB_TOKEN instead of the GitLab token. Plan: search .oompah/tasks and docs for related issues about state_branch_enabled, GitLab forge credentials, state-branch bootstrap/migration, and credential/auth bugs in state branch activation.
---
author: oompah
created: 2026-07-28 14:00
---
Discovery: Duplicate screening complete — OOMPAH-456 is NOT a duplicate.\n\nSearched all .oompah/tasks/ directories, docs/, and plans/ using keywords: state_branch, gitlab, forge_kind, GITHUB_TOKEN, atomic, preflight, dry-run, intake-alias, nodevirt, proj-bbba976d, forge-aware, forge-neutral, credential, activation, projects.html, PATCH boolean.\n\nClosest candidates reviewed (all confirmed distinct):\n\n1. OOMPAH-255 (Archived): Added state_branch_enabled as a plain PATCH checkbox to projects.html — this is the root-cause implementation that OOMPAH-456 identifies as a bug. OOMPAH-255 was intentionally building the checkbox; OOMPAH-456 is describing the bug that results.\n\n2. OOMPAH-259 (Archived): Implemented migration workflow for existing projects including validate_state_branch() with push-access preflight. Did NOT implement GitLab forge-aware credentials for git push, and did NOT make the projects.html UI route through this workflow instead of a raw PATCH.\n\n3. OOMPAH-258 (Archived): Bootstrap for new projects (initialize_state_branch). No GitLab credential handling.\n\n4. OOMPAH-282 (Backlog): Stage A migration failed with UnicodeEncodeError — different bug (encoding, not auth or atomicity).\n\n5. OOMPAH-6 (Archived): Auth error surfacing for GitHub intake bridge — different forge, different feature area.\n\nKey evidence: docs/state-branch-migration.md line 80 contains 'The GitHub token in .env does not have write access to the repository. Update GITHUB_TOKEN and restart.' — confirming the GitHub-specific diagnostic message that OOMPAH-456 identifies as the bug for GitLab projects.\n\nConclusion: OOMPAH-456 is a unique bug combining three new problems not covered by any prior task: (1) UI activation bypasses migration workflow via plain PATCH; (2) git push --dry-run in preflight doesn't use the GitLab project access token; (3) diagnostics incorrectly mention GITHUB_TOKEN for GitLab projects.
---
author: oompah
created: 2026-07-28 14:00
---
Focus handoff: duplicate_detector\n\n1. **Outcome**: OOMPAH-456 is NOT a duplicate. Full search of all task states, docs/, and plans/ confirms this is a new, unique bug report.\n\n2. **Evidence and key files**:\n   - docs/state-branch-migration.md: Contains GitHub-specific GITHUB_TOKEN diagnostic that is wrong for GitLab projects (line ~80)\n   - oompah/templates/projects.html: Has state_branch_enabled as a plain PATCH boolean checkbox (from OOMPAH-255)\n   - oompah/state_branch_migration.py: Has validate_state_branch() and migrate_stage_a/b/c() implemented by OOMPAH-259, but no forge-aware git credentials\n   - oompah/project_bootstrap/__init__.py: Has initialize_state_branch() from OOMPAH-258, also without GitLab credential support\n   - oompah/server.py: PATCH handler for projects treats state_branch_enabled as a plain config update\n   - plans/gitlab-forge-parity.md: GitLab forge parity design doc (state-branch push access mentioned)\n   - docs/project-bootstrap.md: Lists state_branch_push preflight check (line 377 mentions 'Developer access level' — a GitLab concept)\n\n3. **Remaining work**:\n   a. Route projects.html state_branch_enabled UI toggle through the migration/bootstrap workflow (not a naked PATCH)\n   b. Inject forge-aware noninteractive git credentials (derived from project access_token, not embedded in URL or logs) for git push/dry-run operations in state_branch_migration.py and project_bootstrap/__init__.py\n   c. Update all validation and remediation messages to be forge-neutral (no GITHUB_TOKEN references for GitLab projects)\n   d. Make activation atomic: verify remote commit and task layout before flipping state_branch_enabled=true\n   e. Tests: GitLab native-Markdown project with only main, auth and push failure rollback, forge-neutral diagnostics\n\n4. **Recommended next focus**: feature (backend implementation: forge-aware git credentials + atomic activation + forge-neutral error messages + UI routing through migration workflow)
---
author: oompah
created: 2026-07-28 14:00
---
Agent completed successfully in 230s (8768 tokens)
---
author: oompah
created: 2026-07-28 14:00
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 57, Tool calls: 38
- Tokens: 41 in / 8.7K out [8.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 50s
- Log: OOMPAH-456__20260728T135653Z.jsonl
---
author: oompah
created: 2026-07-28 14:00
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 14:00
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 14:00
---
Focus: Frontend Developer
---
<!-- COMMENTS:END -->
