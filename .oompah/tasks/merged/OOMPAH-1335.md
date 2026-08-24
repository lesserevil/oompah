---
id: OOMPAH-1335
type: task
status: Merged
priority: null
title: Remove stale local Git URL rewrites during managed-clone credential sanitation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T21:56:39.839941Z'
updated_at: '2026-08-24T23:37:27.117196Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: ac1c7df9-1451-4dc9-bef5-89f3a580a2cd
  request_fingerprint: 480170a98d186409d1ea6f9a920a742b09780738918f101c6c54c6db917c2491
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-4c771cc6b972
    project_id: proj-14849f1b
    task_id: OOMPAH-1335
    digest: cf12e5b1ba11bbf041369aeaeee9cc8ec566784dbfb3512d345b8078c8053d01
  - version: 1
    audit_id: audit-ee0391b798eb
    project_id: proj-14849f1b
    task_id: OOMPAH-1335
    digest: cf12e5b1ba11bbf041369aeaeee9cc8ec566784dbfb3512d345b8078c8053d01
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1335","audit-4c771cc6b972","attempt-387e50ad4d02"]': '2026-08-24T22:49:28.600911+00:00'
    '["proj-14849f1b","OOMPAH-1335","audit-ee0391b798eb","attempt-a88132fd5e76"]': '2026-08-24T23:37:14.907851+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1335
    target_state: Done
    evidence_fingerprint: cf12e5b1ba11bbf041369aeaeee9cc8ec566784dbfb3512d345b8078c8053d01
    workflow_revision: null
    selected_ref: origin/OOMPAH-1335
    selected_sha: 76fe97764a3b56bf7d922eabd49cd8f94844f1e3
    landing_revision: null
    audit_ids:
    - audit-4c771cc6b972
    kind: result
    applied: true
    retired_at: '2026-08-24T22:49:28.600929+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1335
    target_state: Merged
    evidence_fingerprint: cf12e5b1ba11bbf041369aeaeee9cc8ec566784dbfb3512d345b8078c8053d01
    workflow_revision: null
    selected_ref: origin/OOMPAH-1335
    selected_sha: 76fe97764a3b56bf7d922eabd49cd8f94844f1e3
    landing_revision: null
    audit_ids:
    - audit-ee0391b798eb
    kind: result
    applied: true
    retired_at: '2026-08-24T23:37:14.907871+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1335
    audit_id: audit-4c771cc6b972
    attempt_id: attempt-387e50ad4d02
    target_state: Done
    evidence_fingerprint: cf12e5b1ba11bbf041369aeaeee9cc8ec566784dbfb3512d345b8078c8053d01
    status: In Validation
    audit_ids:
    - audit-4c771cc6b972
    kind: result
    applied: true
    created_at: '2026-08-24T22:49:28.600940+00:00'
    applied_at: '2026-08-24T22:49:36.436895+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1335
    audit_id: audit-ee0391b798eb
    attempt_id: attempt-a88132fd5e76
    target_state: Merged
    evidence_fingerprint: cf12e5b1ba11bbf041369aeaeee9cc8ec566784dbfb3512d345b8078c8053d01
    status: Merged
    audit_ids:
    - audit-ee0391b798eb
    kind: result
    applied: true
    created_at: '2026-08-24T23:37:14.907883+00:00'
    applied_at: '2026-08-24T23:37:25.807830+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-4c771cc6b972
    project_id: proj-14849f1b
    task_id: OOMPAH-1335
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cf12e5b1ba11bbf041369aeaeee9cc8ec566784dbfb3512d345b8078c8053d01
    attempts:
    - version: 1
      attempt_id: attempt-387e50ad4d02
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: cf12e5b1ba11bbf041369aeaeee9cc8ec566784dbfb3512d345b8078c8053d01
      created_at: '2026-08-24T22:37:38.119482+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T22:37:38.119482+00:00'
      branch_key: OOMPAH-1335
      selected_ref: origin/OOMPAH-1335
      selected_sha: 76fe97764a3b56bf7d922eabd49cd8f94844f1e3
      verdict: pass
      completed_at: '2026-08-24T22:49:28.600756+00:00'
      ended_at: '2026-08-24T22:49:28.600756+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T22:23:59.513120+00:00'
    eligible_at: '2026-08-24T22:23:59.513120+00:00'
    selected_ref: origin/OOMPAH-1335
    selected_sha: 76fe97764a3b56bf7d922eabd49cd8f94844f1e3
    updated_at: '2026-08-24T22:49:28.600756+00:00'
  - version: 1
    audit_id: audit-ee0391b798eb
    project_id: proj-14849f1b
    task_id: OOMPAH-1335
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cf12e5b1ba11bbf041369aeaeee9cc8ec566784dbfb3512d345b8078c8053d01
    attempts:
    - version: 1
      attempt_id: attempt-a88132fd5e76
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: cf12e5b1ba11bbf041369aeaeee9cc8ec566784dbfb3512d345b8078c8053d01
      created_at: '2026-08-24T22:50:03.237004+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T22:50:03.237004+00:00'
      branch_key: OOMPAH-1335
      selected_ref: origin/OOMPAH-1335
      selected_sha: 76fe97764a3b56bf7d922eabd49cd8f94844f1e3
      verdict: pass
      completed_at: '2026-08-24T23:37:14.907672+00:00'
      ended_at: '2026-08-24T23:37:14.907672+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T22:23:59.513120+00:00'
    prerequisite_audit_id: audit-4c771cc6b972
    selected_ref: origin/OOMPAH-1335
    selected_sha: 76fe97764a3b56bf7d922eabd49cd8f94844f1e3
    updated_at: '2026-08-24T23:37:14.907672+00:00'
    eligible_at: '2026-08-24T22:49:28.600756+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-387e50ad4d02
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cf12e5b1ba11bbf041369aeaeee9cc8ec566784dbfb3512d345b8078c8053d01
    created_at: '2026-08-24T22:37:38.119482+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T22:37:38.119482+00:00'
    branch_key: OOMPAH-1335
    selected_ref: origin/OOMPAH-1335
    selected_sha: 76fe97764a3b56bf7d922eabd49cd8f94844f1e3
  - version: 1
    attempt_id: attempt-a88132fd5e76
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cf12e5b1ba11bbf041369aeaeee9cc8ec566784dbfb3512d345b8078c8053d01
    created_at: '2026-08-24T22:50:03.237004+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T22:50:03.237004+00:00'
    branch_key: OOMPAH-1335
    selected_ref: origin/OOMPAH-1335
    selected_sha: 76fe97764a3b56bf7d922eabd49cd8f94844f1e3
oompah.lifecycle_revision: 2
oompah.task_costs:
  total_input_tokens: 242
  total_output_tokens: 9349
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 242
      output_tokens: 9349
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 242
    output_tokens: 9349
    cost_usd: 0.0
    recorded_at: '2026-08-24T22:49:57.490013+00:00'
---
## Summary

A managed native Markdown project (trickle, proj-3e4e9214) had canonical repo_url=https://gitlab-master.nvidia.com/omniverse/devplat/trickle.git and remote.origin.url correctly normalized to HTTPS, but its managed clone .git/config retained a local url.git@gitlab-master.nvidia.com:.insteadof=https://gitlab-master.nvidia.com/ rewrite. Every state-branch fetch was silently rewritten back to SSH, which failed with publickey/incorrect-port (12051) and made `oompah task create --project proj-3e4e9214` return HTTP 500. Existing sanitize_managed_clone_credentials removes remote userinfo, credential helpers, and http.*.extraheader and normalizes origin, but does not remove local url.*.insteadof rewrite routes. Implement fail-closed sanitation of managed-clone/worktree-local url.*.insteadof entries that rewrite the canonical project repo URL/host to another transport or credential-bearing route, without altering unrelated global config or unrelated remotes. Ensure clone/adopt/migrate/self-heal/direct-maintenance call sites apply it. Regression: local insteadOf rewrites HTTPS canonical GitLab URL to SSH; sanitation removes it; git remote get-url and state-branch fetch use canonical HTTPS; task creation succeeds. Preserve benign unrelated url rewrites. Acceptance: canonical project repo_url cannot be overridden by stale local insteadOf config, and no agent gains a direct push/credential route.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 22:24
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-24 22:37
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-24 22:37
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 22:49
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- test_results: All 21 tests in test_managed_git_credentials.py passed
- critical_regressions: test_sanitize_managed_clone_removes_canonical_url_rewrite and test_sanitize_managed_clone_preserves_unrelated_url_rewrite both pass
- implementation: New _url_rewrite_matches_canonical() helper and enhanced sanitize_managed_clone_credentials() that removes only repository-local url.*.insteadOf entries matching canonical URL
- call_sites: Integrated in create(), _create_epic_worktree_locked(), _prepare_existing_epic_worktree()
- requirements: Fail-closed sanitation, local entries only, canonical URL protection, preserve unrelated config, idempotent, HTTPS-to-SSH removal, all call sites integrated
---
author: oompah
created: 2026-08-24 22:49
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 64, Tool calls: 29
- Tokens: 242 in / 9.3K out [9.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 12m 16s
- Log: OOMPAH-1335__20260824T223804Z.jsonl
---
author: oompah
created: 2026-08-24 22:50
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-24 22:50
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 23:37
---
Audit PASS — Merged

OOMPAH-1335 implementation complete and verified. Commit 76fe97764a3b56bf7d922eabd49cd8f94844f1e3 removes stale local Git URL rewrites during managed-clone credential sanitation. All critical functionality tests pass.

Safe evidence:
- commit_sha: 76fe97764a3b56bf7d922eabd49cd8f94844f1e3
- commit_message: OOMPAH-1335: remove canonical URL rewrites from managed clones
- helper_function: _url_rewrite_matches_canonical() added to git_credentials.py
- sanitization_enhanced: sanitize_managed_clone_credentials() removes repository-local url.*.insteadOf entries
- call_site_1: ProjectStore.create() at line 2525 with canonical_url parameter
- call_site_2: _create_epic_worktree_locked() at line 6803-6806 with project.repo_url
- call_site_3: _prepare_existing_epic_worktree() at line 6894-6897 with project.repo_url
- unit_tests_passed: 21 tests in test_managed_git_credentials.py
- regression_test_1: test_sanitize_managed_clone_removes_canonical_url_rewrite PASSED
- regression_test_2: test_sanitize_managed_clone_preserves_unrelated_url_rewrite PASSED
- integration_tests: 164 tests in test_projects.py all passed
- fail_closed: implemented with try-except error handling
- local_only: uses --local flag to avoid affecting global config
- canonical_protected: via _url_rewrite_matches_canonical() prefix matching
- idempotent: verified by test_sanitize_managed_clone_is_idempotent
- https_to_ssh_fixed: verified by test_sanitize_managed_clone_removes_canonical_url_rewrite
- unrelated_preserved: verified by test_sanitize_managed_clone_preserves_unrelated_url_rewrite
---
<!-- COMMENTS:END -->
