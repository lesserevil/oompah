---
id: OOMPAH-409
type: task
status: Archived
priority: null
title: Allow Codex conflict resolvers to write shared git metadata
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T15:36:41.250138Z'
updated_at: '2026-08-02T01:28:33.129535Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-6354109fe487: '2026-08-02T01:28:27.871379+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-409
    target_state: Archived
    evidence_fingerprint: e8ff423b9fd8311a0955295c74019a295b83f02baf15a59c70743f840ac83527
    audit_ids:
    - audit-8a06b236dc99
    kind: result
    applied: true
    retired_at: '2026-08-02T01:28:27.871390+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-409
    audit_id: audit-8a06b236dc99
    attempt_id: attempt-6354109fe487
    target_state: Archived
    evidence_fingerprint: e8ff423b9fd8311a0955295c74019a295b83f02baf15a59c70743f840ac83527
    status: Archived
    audit_ids:
    - audit-8a06b236dc99
    applied: true
    created_at: '2026-08-02T01:28:27.871407+00:00'
    applied_at: '2026-08-02T01:28:32.295627+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-8a06b236dc99
    project_id: proj-14849f1b
    task_id: OOMPAH-409
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e8ff423b9fd8311a0955295c74019a295b83f02baf15a59c70743f840ac83527
    attempts:
    - version: 1
      attempt_id: attempt-6354109fe487
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e8ff423b9fd8311a0955295c74019a295b83f02baf15a59c70743f840ac83527
      created_at: '2026-08-02T01:16:02.331290+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:16:02.331290+00:00'
      branch_key: OOMPAH-409
      verdict: pass
      completed_at: '2026-08-02T01:28:27.871176+00:00'
      ended_at: '2026-08-02T01:28:27.871176+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:23.256045+00:00'
    updated_at: '2026-08-02T01:28:27.871176+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-6354109fe487
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e8ff423b9fd8311a0955295c74019a295b83f02baf15a59c70743f840ac83527
    created_at: '2026-08-02T01:16:02.331290+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:16:02.331290+00:00'
    branch_key: OOMPAH-409
---
## Summary

Fix the Codex ACP workspace-write sandbox for git worktrees. Conflict resolver agents can write the per-worktree git metadata directory but git rebase/fetch also needs locks in the shared common .git directory; this currently yields read-only filesystem errors and agents exit without resolving PRs. Grant only the resolved common git directory in addition to per-worktree metadata, with safe path validation and tests. Acceptance criteria: worktree-backed Codex CLI sessions receive both required writable git metadata paths; a resolver can execute rebase/fetch without sandbox read-only lock failures; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 15:37
---
Fixed Codex ACP worktree sandbox permissions: sessions now grant the worktree gitdir and Git's resolved common .git metadata directory from commondir, allowing fetch/rebase lock files without granting repository working files. Added coverage for valid and invalid common-dir resolution. Verification: make test passed.
---
author: oompah
created: 2026-07-22 15:38
---
Granted required shared Git metadata path for Codex worktree resolver sessions; tests added and make test passed.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: Codex worktree access to required common Git metadata is present on origin/main in commit 3d5b347ec. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:28
---
Verified delivered on origin/main in 3d5b347ec and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:13
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:16
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:16
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:28
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: 3d5b347ecf44d21eb097b39daffd139eb4f72ad7
- delivery_title: Allow Codex worktrees to write common Git metadata
- delivery_ancestor_of_origin_main: yes (present in git log origin/main -- oompah/acp_backends/codex.py)
- origin_main_head: 6252b5434f392b74de9703a9fc8dca1951dfeaca
- implementation_file: oompah/acp_backends/codex.py
- implementation_function: _get_worktree_git_write_dirs (lines 260-288)
- wiring_site: CodexAcpBackendSession start-thread additional_directories (line 806)
- test_file: tests/test_acp_codex_backend.py
- test_class: TestCodexCliAdditionalDirectories
- test_focused_result: 7 passed, 56 deselected (0.55s)
- new_regression_test: test_omits_missing_or_invalid_common_dir
- commondir_safety_checks: os.path.isabs + normpath, os.path.realpath, os.path.isdir, dedup vs gitdir realpath
---
<!-- COMMENTS:END -->
