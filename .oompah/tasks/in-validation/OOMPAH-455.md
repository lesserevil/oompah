---
id: OOMPAH-455
type: bug
status: In Validation
priority: 1
title: Make GitLab project edits use one intake alias and forge-aware identity resolution
parent: OOMPAH-451
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
- focus-complete:frontend
assignee: null
created_at: '2026-07-28T12:34:53.400428Z'
updated_at: '2026-08-04T15:31:06.565920Z'
work_branch: epic-OOMPAH-451
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 64a396b2-aa5a-4bd8-afe5-9fe6e62f85b0
oompah.work_branch: epic-OOMPAH-451
oompah.task_costs:
  total_input_tokens: 513917
  total_output_tokens: 23979
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 513917
      output_tokens: 23979
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 28
    output_tokens: 6141
    cost_usd: 0.0
    recorded_at: '2026-07-28T13:31:08.641652+00:00'
  - profile: default
    model: unknown
    input_tokens: 513844
    output_tokens: 2413
    cost_usd: 0.0
    recorded_at: '2026-07-28T13:33:05.918597+00:00'
  - profile: deep
    model: unknown
    input_tokens: 45
    output_tokens: 15425
    cost_usd: 0.0
    recorded_at: '2026-07-28T13:43:28.511825+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-46f9be89689a
    project_id: proj-14849f1b
    task_id: OOMPAH-455
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d157a76b965e6405e8848d7e03640eebf4e3b466fec3a116fba8fbaab4f000fc
    attempts:
    - version: 1
      attempt_id: attempt-8ff166268307
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d157a76b965e6405e8848d7e03640eebf4e3b466fec3a116fba8fbaab4f000fc
      created_at: '2026-08-04T15:30:37.585804+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T15:30:37.585804+00:00'
      branch_key: epic-OOMPAH-451
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T15:19:29.046464+00:00'
    updated_at: '2026-08-04T15:30:37.585804+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-8ff166268307
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d157a76b965e6405e8848d7e03640eebf4e3b466fec3a116fba8fbaab4f000fc
    created_at: '2026-08-04T15:30:37.585804+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T15:30:37.585804+00:00'
    branch_key: epic-OOMPAH-451
---
## Summary

Problem: the Projects editor always sends both github_issue_intake_enabled and external_issue_intake_enabled. ProjectStore explicitly rejects both, so any edit, including enabling state_branch_enabled, fails with Specify only one error even when both values are false and equal. The same save path also calls the GitHub token-owner API when status_actor_login is blank, generating GitHub 401 warnings for a valid GitLab token.

Implementation scope: send one canonical forge-neutral intake field from oompah/templates/projects.html; make the PATCH compatibility contract deterministic for legacy and neutral clients; resolve actor identity with the configured forge provider or leave it unset without calling another forge. Ensure editing unrelated settings does not rewrite or validate unrelated aliases. Relevant files include oompah/templates/projects.html, oompah/server.py, oompah/projects.py, and project CRUD/GitLab UI tests.

Tests: reproduce editing a GitLab project with both stored intake aliases represented in the GET response, enable state_branch_enabled through the UI payload, assert a successful update, and assert no GitHub identity call; cover legacy GitHub clients and conflicting alias values explicitly; run make test.

Acceptance criteria: enabling the state branch for nodevirt succeeds from the Projects page; matching compatibility aliases never block unrelated edits; conflicting values receive a precise validation error; GitLab credentials are never sent to GitHub.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 13:28
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 13:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 13:30
---
Duplicate investigation complete: No duplicate found.

Searched across all .oompah/tasks/ states (archived, merged, open, backlog — 280+ tasks) and plans/ docs/ using keywords: github_issue_intake_enabled, external_issue_intake_enabled, Specify only one, intake alias, forge-aware, forge identity, status_actor_login, state_branch_enabled, nodevirt, Projects editor, GitLab 401, token owner, PATCH project, intake_enabled.

Zero matches across all search patterns. OOMPAH-455 describes a novel bug specific to the Projects UI editor sending both intake alias fields simultaneously, causing ProjectStore validation failure.

Closest candidate reviewed and ruled out:
- plans/gitlab-forge-parity.md — a large design plan that mentions generalizing github_issue_intake_enabled → external_issue_intake_enabled as a future architecture goal, but contains no task or fix for the specific bug described here (simultaneous alias sending blocking unrelated edits).

No existing task covers the same failure mode (ProjectStore rejecting both intake aliases simultaneously, or GitHub 401 warnings from GitLab token resolving via GitHub API).

Relevant files for implementation:
- oompah/templates/projects.html — UI sends both intake fields; needs to send only one canonical forge-neutral field
- oompah/server.py — PATCH handler; needs compatibility alias contract and forge-aware identity resolution
- oompah/projects.py — ProjectStore validation; needs deterministic alias normalization
- tests/ — need GitLab project edit test, legacy GitHub client test, conflicting alias test

Next focus: backend (bug fix + tests)
---
author: oompah
created: 2026-07-28 13:31
---
Agent completed successfully in 140s (6169 tokens)
---
author: oompah
created: 2026-07-28 13:31
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 64, Tool calls: 40
- Tokens: 28 in / 6.1K out [6.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 20s
- Log: OOMPAH-455__20260728T132851Z.jsonl
---
author: oompah
created: 2026-07-28 13:31
---
Focus handoff required before leaving `duplicate_detector`. Add a comment headed `Focus handoff: duplicate_detector` with outcome, evidence, remaining work, and next focus.
---
author: oompah
created: 2026-07-28 13:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 13:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 13:32
---
Understanding: This run is limited to duplicate screening and the required duplicate_detector handoff. I am verifying whether any prior task covers the simultaneous intake-alias PATCH failure or cross-forge token-owner lookup; if none does, I will label this focus complete without modifying code.
---
author: oompah
created: 2026-07-28 13:32
---
Focus handoff: duplicate_detector

Outcome: No duplicate found. OOMPAH-455 is a novel bug and should proceed to implementation.

Evidence: Re-searched .oompah/tasks, docs, and plans for github_issue_intake_enabled, external_issue_intake_enabled, status_actor_login, state_branch_enabled, intake aliases, token-owner/API identity lookup, GitLab 401, and the 'Specify only one' error. OOMPAH-255 was read in full: it introduced state_branch_enabled model/API/UI support, but does not cover simultaneous intake aliases or forge-aware identity resolution. OOMPAH-6 was read in full: it covers a real GitHub intake token failure and actionable auth reporting, not a GitLab project token being sent to GitHub during an unrelated Projects edit. plans/gitlab-forge-parity.md specifies external_issue_intake_enabled with a legacy GitHub alias, but contains no implementation/task for deterministic PATCH alias normalization or provider-aware actor resolution.

Remaining work: Update oompah/templates/projects.html to submit one canonical forge-neutral intake field; make server/ProjectStore PATCH compatibility deterministic so matching legacy+neutral aliases do not block unrelated edits while conflicts return a precise error; resolve blank status_actor_login through only the configured forge (or leave unset); add GitLab UI/CRUD regressions plus legacy GitHub and conflicting-alias tests; run make test. No code was changed in this duplicate-screening run.

Recommended next focus: feature, covering the backend/UI compatibility fix and regression tests.
---
author: oompah
created: 2026-07-28 13:33
---
Agent completed successfully in 102s (516257 tokens)
---
author: oompah
created: 2026-07-28 13:33
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 12
- Tokens: 513.8K in / 2.4K out [516.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 42s
- Log: OOMPAH-455__20260728T133125Z.jsonl
---
author: oompah
created: 2026-07-28 13:33
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 13:33
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 13:33
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-28 13:33
---
Understanding: As the Frontend Developer focus, my job is to fix oompah/templates/projects.html to send only ONE canonical forge-neutral intake field (external_issue_intake_enabled) instead of both github_issue_intake_enabled and external_issue_intake_enabled simultaneously. ProjectStore rejects payloads with both fields. I will also check what else the form submits that may trigger cross-forge API calls. Plan: (1) read projects.html to understand the current form structure, (2) identify where both intake fields are submitted, (3) update the form/JS to submit only external_issue_intake_enabled, (4) ensure the UI still shows correctly for GitHub and GitLab projects, (5) run make test.
---
author: oompah
created: 2026-07-28 13:36
---
Discovery: Root cause confirmed in oompah/templates/projects.html. In saveProject() (line ~805), the PATCH body always includes BOTH github_issue_intake_enabled AND external_issue_intake_enabled with the same value. server.py passes both to ProjectStore.update() fields dict; ProjectStore.update() at projects.py:1343 rejects any payload where both fields are present with 'Specify only one...' error - even when both values are false and equal. Fix: remove github_issue_intake_enabled from the saveProject body; send only external_issue_intake_enabled (the canonical forge-neutral field). server.py already handles external_issue_intake_enabled in the PATCH handler (lines 10375-10377) and passes it to ProjectStore which normalizes it internally. Backend status_actor_login issue: server.py lines 10518-10530 call _resolve_github_token_owner() regardless of forge_kind, sending GitLab tokens to GitHub API - this needs a backend fix (forge-aware check before calling). Will implement frontend fix now and note backend work for handoff.
---
author: oompah
created: 2026-07-28 13:41
---
Implementation: Fixed oompah/templates/projects.html saveProject() function. Removed github_issue_intake_enabled from the PATCH body — it was being sent alongside external_issue_intake_enabled (the canonical forge-neutral field), causing ProjectStore.update() to raise 'Specify only one' for every save from the Projects page, including unrelated edits like enabling state_branch_enabled. The fix: send only external_issue_intake_enabled. The server PATCH handler already routes this field through ProjectStore which normalizes it internally. Card display still reads both aliases (OR) for backward compatibility with stored data. Added TestSaveProjectIntakeAliasPayload class to tests/test_projects_gitlab_ui.py with 4 tests covering: external alias is sent, legacy alias is absent from PATCH body, checkbox value maps to canonical field, and backward-compat card display reads both.
---
author: oompah
created: 2026-07-28 13:42
---
Verification: make test passed — 12333 passed, 39 skipped in 236.81s. All 76 tests in test_projects_gitlab_ui.py pass including the 4 new TestSaveProjectIntakeAliasPayload tests. Frontend fix is complete. Backend work remaining (outside frontend scope): (1) server.py PATCH handler calls _resolve_github_token_owner() for GitLab projects when status_actor_login is blank — sends GitLab token to GitHub API generating 401 warnings; needs forge_kind check before calling (lines 10518-10530 and 10633-10637 in server.py); (2) tests that reproduce the GitLab project edit end-to-end via HTTP (server-level integration test with mock GitHub identity call assertion). These require a backend/feature focus.
---
author: oompah
created: 2026-07-28 13:43
---
Focus handoff: frontend

Outcome: Frontend fix complete and pushed. The core bug (Projects editor blocking any save with 'Specify only one' error) is resolved.

Files changed:
- oompah/templates/projects.html: Removed github_issue_intake_enabled from saveProject() PATCH body; now sends only external_issue_intake_enabled (canonical forge-neutral field). Added comment explaining the invariant.
- tests/test_projects_gitlab_ui.py: Added TestSaveProjectIntakeAliasPayload class (4 tests) verifying the correct PATCH payload behavior including that the legacy alias is absent from the body.

Evidence: make test passed (12333 passed, 39 skipped). All 76 tests in test_projects_gitlab_ui.py pass.

Remaining work for backend focus:
1. server.py forge-aware status_actor_login: Lines 10518-10530 and 10633-10637 call _resolve_github_token_owner() unconditionally when status_actor_login is blank or access_token is updated. For GitLab projects (forge_kind='gitlab'), this sends the GitLab token to GitHub's API generating 401 warnings. Fix: check effective forge_kind (fields.get('forge_kind', existing_project.forge_kind)) before calling _resolve_github_token_owner(); for non-github forges, leave status_actor_login as-is (None/unchanged) without calling the GitHub API.
2. Server-level integration tests: reproduce editing a GitLab project with both intake aliases in stored data, enable state_branch_enabled, assert 200 response, assert _resolve_github_token_owner is never called. Cover legacy GitHub clients (send only github_issue_intake_enabled), conflicting aliases (send both with different values → precise error), GitLab blank status_actor_login (no GitHub call). Run make test.

Recommended next focus: feature (backend + server integration tests).
---
author: oompah
created: 2026-07-28 13:43
---
Agent completed successfully in 612s (15470 tokens)
---
author: oompah
created: 2026-07-28 13:43
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/default]
- Turns: 87, Tool calls: 54
- Tokens: 45 in / 15.4K out [15.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 10m 12s
- Log: OOMPAH-455__20260728T133319Z.jsonl
---
author: oompah
created: 2026-07-28 13:43
---
Focus handoff from `frontend` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 13:43
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 13:43
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 13:43
---
Understanding: Continuing from the completed frontend fix. I will inspect the existing branch changes, make PATCH intake-alias handling deterministic (accept one alias or matching aliases, reject conflicts precisely), prevent GitLab project edits from invoking GitHub token-owner resolution, add focused server/ProjectStore regressions, run make test, commit, push, and close the task.
---
author: oompah
created: 2026-07-28 13:44
---
Discovery: The frontend commit is present and the worktree is clean. ProjectStore.update() currently rejects any payload containing both intake aliases before comparing values. api_update_project() also calls _resolve_github_token_owner() for explicit blank actors and token changes without checking the effective forge; api_create_project() has the same cross-forge fallback. The fix will keep github_issue_intake_enabled as the persisted field, accept either alias and coalesce matching dual values, reject differing dual values with a precise conflict error, and invoke the GitHub resolver only when the effective forge is github.
---
author: oompah
created: 2026-07-28 13:52
---
Implementation: Updated ProjectStore intake-alias normalization to keep the legacy persisted field while accepting neutral-only, legacy-only, or matching dual-alias PATCHes and returning an explicit conflict error for differing values. Updated project create/PATCH identity fallback so _resolve_github_token_owner runs only for the effective github forge; GitLab blank actors remain unset and GitLab token changes never invoke GitHub. Added CRUD regressions for the GitLab UI state-branch edit, GitLab create/token update, both client aliases, matching values, conflicts, and invalid neutral values; refreshed the frontend comment to describe the canonical single-field payload.
---
author: oompah
created: 2026-07-28 13:52
---
Verification: The Makefile test target could not start because the installed snap-backed uv failed to create a transient DBus scope (exit 46), so I ran the target's equivalent command with the repository virtualenv. Full suite passed: 12,342 passed, 39 skipped, 12 warnings in 239.14s. Focused project CRUD/GitLab UI suite then passed: 233 passed, 1 warning in 2.07s. No test failures.
---
author: oompah
created: 2026-07-28 13:54
---
Completion: Delivered and pushed commit 48a793f90. The Projects editor sends only external_issue_intake_enabled; PATCH accepts legacy-only, neutral-only, and matching aliases while rejecting conflicts precisely; GitLab create/edit/token paths never call GitHub token-owner resolution and leave blank actors unset. Full suite passed (12,342 passed, 39 skipped), post-rebase focused CRUD/UI suite passed (233 passed), and the branch is synchronized with origin (+0/-0). The repository secret target's only finding was an unchanged REDACTED test fixture false positive.
---
author: oompah
created: 2026-07-28 13:54
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/default]
- Turns: 0, Tool calls: 47
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 11m 13s
- Log: OOMPAH-455__20260728T134343Z.jsonl
---
author: oompah
created: 2026-07-28 13:54
---
Made project intake aliases deterministic and identity lookup forge-aware; GitLab Projects-page state-branch edits now succeed without GitHub credential calls. Added comprehensive CRUD/UI regressions and pushed commit 48a793f90.
---
author: oompah
created: 2026-08-04 15:19
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 15:31
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 15:31
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
