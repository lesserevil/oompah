---
id: OOMPAH-619
type: epic
status: Archived
priority: 1
title: Unify CLI authentication sources and align the installed client
parent: null
children:
- OOMPAH-620
- OOMPAH-621
- OOMPAH-623
- OOMPAH-624
- OOMPAH-650
- OOMPAH-660
- OOMPAH-662
blocked_by: []
start_blocked_by: []
labels:
- rebase-requested
- epic:rebasing
assignee: null
created_at: '2026-07-30T21:24:41.452666Z'
updated_at: '2026-08-07T22:35:57.900157Z'
work_branch: epic-OOMPAH-619
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/626
review_number: '626'
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-3a4b0536b50d: '2026-07-31T15:00:12.993955+00:00'
    attempt-88d6cfdc81a5: '2026-07-31T21:33:47.207022+00:00'
    attempt-2d0b94872e3f: '2026-08-07T22:35:46.164123+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-619
    target_state: Done
    evidence_fingerprint: a0a813b257073a0b1699ed144144a8a44b89e75cd90141bd2f0965d3fcfbb03a
    audit_ids:
    - audit-3b0770c606df
    kind: result
    applied: true
    retired_at: '2026-07-31T15:00:12.993965+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-619
    target_state: Merged
    evidence_fingerprint: 1d9f9ae25f9f29d848983bc5d59fc7e1f851798edb3062d62564d7400934cad4
    audit_ids:
    - audit-a04daf8508ab
    kind: result
    applied: true
    retired_at: '2026-07-31T21:33:47.207045+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-619
    target_state: Archived
    evidence_fingerprint: c5cf9a080b29a7e60084087fea03010defa018005ff5b6ee2b5b4b600e0b455e
    audit_ids:
    - audit-08210eeb9df6
    kind: result
    applied: true
    retired_at: '2026-08-07T22:35:46.164139+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-619
    audit_id: audit-3b0770c606df
    attempt_id: attempt-3a4b0536b50d
    target_state: Done
    evidence_fingerprint: a0a813b257073a0b1699ed144144a8a44b89e75cd90141bd2f0965d3fcfbb03a
    status: Done
    audit_ids:
    - audit-3b0770c606df
    applied: true
    created_at: '2026-07-31T15:00:12.993978+00:00'
    applied_at: '2026-07-31T15:00:18.123318+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-619
    audit_id: audit-a04daf8508ab
    attempt_id: attempt-88d6cfdc81a5
    target_state: Merged
    evidence_fingerprint: 1d9f9ae25f9f29d848983bc5d59fc7e1f851798edb3062d62564d7400934cad4
    status: Merged
    audit_ids:
    - audit-a04daf8508ab
    applied: true
    created_at: '2026-07-31T21:33:47.207068+00:00'
    applied_at: '2026-07-31T21:33:52.081337+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-619
    audit_id: audit-08210eeb9df6
    attempt_id: attempt-2d0b94872e3f
    target_state: Archived
    evidence_fingerprint: c5cf9a080b29a7e60084087fea03010defa018005ff5b6ee2b5b4b600e0b455e
    status: Archived
    audit_ids:
    - audit-08210eeb9df6
    kind: result
    applied: true
    created_at: '2026-08-07T22:35:46.164159+00:00'
    applied_at: '2026-08-07T22:35:55.245953+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-3b0770c606df
    project_id: proj-14849f1b
    task_id: OOMPAH-619
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a0a813b257073a0b1699ed144144a8a44b89e75cd90141bd2f0965d3fcfbb03a
    attempts:
    - version: 1
      attempt_id: attempt-3a4b0536b50d
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a0a813b257073a0b1699ed144144a8a44b89e75cd90141bd2f0965d3fcfbb03a
      created_at: '2026-07-31T14:49:46.247336+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T14:49:46.247336+00:00'
      branch_key: OOMPAH-619
      verdict: pass
      completed_at: '2026-07-31T15:00:12.993754+00:00'
      ended_at: '2026-07-31T15:00:12.993754+00:00'
    requested_by:
      version: 1
      identity: orchestrator
    previous_state: Open
    created_at: '2026-07-31T14:49:39.308179+00:00'
    updated_at: '2026-07-31T15:00:12.993754+00:00'
  - version: 1
    audit_id: audit-a04daf8508ab
    project_id: proj-14849f1b
    task_id: OOMPAH-619
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1d9f9ae25f9f29d848983bc5d59fc7e1f851798edb3062d62564d7400934cad4
    attempts:
    - version: 1
      attempt_id: attempt-f29c6915ad41
      target_state: Merged
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 1d9f9ae25f9f29d848983bc5d59fc7e1f851798edb3062d62564d7400934cad4
      created_at: '2026-07-31T21:29:00.814614+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T21:29:00.814614+00:00'
      branch_key: epic-OOMPAH-619
      ended_at: '2026-07-31T21:30:38.582642+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-88d6cfdc81a5
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 1d9f9ae25f9f29d848983bc5d59fc7e1f851798edb3062d62564d7400934cad4
      created_at: '2026-07-31T21:30:39.865869+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-07-31T21:30:39.865869+00:00'
      branch_key: epic-OOMPAH-619
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-07-31T21:33:47.206790+00:00'
      ended_at: '2026-07-31T21:33:47.206790+00:00'
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T21:27:50.017008+00:00'
    updated_at: '2026-07-31T21:33:47.206790+00:00'
  - version: 1
    audit_id: audit-08210eeb9df6
    project_id: proj-14849f1b
    task_id: OOMPAH-619
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c5cf9a080b29a7e60084087fea03010defa018005ff5b6ee2b5b4b600e0b455e
    attempts:
    - version: 1
      attempt_id: attempt-2d0b94872e3f
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c5cf9a080b29a7e60084087fea03010defa018005ff5b6ee2b5b4b600e0b455e
      created_at: '2026-08-07T21:54:42.952839+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-07T21:54:42.952839+00:00'
      branch_key: epic-OOMPAH-619
      selected_ref: origin/main
      selected_sha: bb82f7f39510f0e02886307291812f2f8b3e6901
      verdict: pass
      completed_at: '2026-08-07T22:35:46.163943+00:00'
      ended_at: '2026-08-07T22:35:46.163943+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-07T21:53:53.021531+00:00'
    selected_ref: origin/main
    selected_sha: bb82f7f39510f0e02886307291812f2f8b3e6901
    updated_at: '2026-08-07T22:35:46.163943+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-3a4b0536b50d
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a0a813b257073a0b1699ed144144a8a44b89e75cd90141bd2f0965d3fcfbb03a
    created_at: '2026-07-31T14:49:46.247336+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T14:49:46.247336+00:00'
    branch_key: OOMPAH-619
  - version: 1
    attempt_id: attempt-f29c6915ad41
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1d9f9ae25f9f29d848983bc5d59fc7e1f851798edb3062d62564d7400934cad4
    created_at: '2026-07-31T21:29:00.814614+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T21:29:00.814614+00:00'
    branch_key: epic-OOMPAH-619
    ended_at: '2026-07-31T21:30:38.582642+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-88d6cfdc81a5
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1d9f9ae25f9f29d848983bc5d59fc7e1f851798edb3062d62564d7400934cad4
    created_at: '2026-07-31T21:30:39.865869+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-07-31T21:30:39.865869+00:00'
    branch_key: epic-OOMPAH-619
    candidate_rotation_count: 1
  - version: 1
    attempt_id: attempt-2d0b94872e3f
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c5cf9a080b29a7e60084087fea03010defa018005ff5b6ee2b5b4b600e0b455e
    created_at: '2026-08-07T21:54:42.952839+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-07T21:54:42.952839+00:00'
    branch_key: epic-OOMPAH-619
    selected_ref: origin/main
    selected_sha: bb82f7f39510f0e02886307291812f2f8b3e6901
oompah.task_costs:
  total_input_tokens: 139
  total_output_tokens: 26101
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 139
      output_tokens: 26101
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 83
    output_tokens: 24712
    cost_usd: 0.0
    recorded_at: '2026-07-31T15:00:29.229888+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 12
    output_tokens: 16
    cost_usd: 0.0
    recorded_at: '2026-07-31T21:29:23.583894+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 44
    output_tokens: 1373
    cost_usd: 0.0
    recorded_at: '2026-07-31T21:34:12.010246+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/626
oompah.review_number: '626'
oompah.work_branch: epic-OOMPAH-619
oompah.target_branch: main
---
## Summary

Deliver a standalone Oompah CLI whose HTTP Basic credentials can be supplied explicitly on the command line, through environment variables, or from the machine entry in the default user netrc file. Preserve the existing password-file source and embedded-URL rejection. Define deterministic precedence, fail closed on partial or conflicting credentials, and never include passwords in logs, tracebacks, HTTP errors, telemetry, shell completion, or task comments. Because a plaintext command-line password is visible to other same-host process inspectors, help and operator documentation must warn about that exposure and recommend password-file or netrc for normal use. Apply the same resolver to task and admin HTTP clients, retain unauthenticated-server compatibility, and cover source selection, server URL hostname matching, permissions and malformed netrc behavior, redaction, 401 remediation, and cross-surface requests with tests. After all children are audited and the epic reaches main, the operator will reinstall the standalone CLI from that exact main revision on this host and verify authenticated task view plus admin status against the running server.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:32
---
Operator clarification: ~/.local/bin/oompah is the canonical system CLI, not the project virtualenv executable. This epic is incomplete until the canonical binary is installed from the same merged main revision as the deployed server and lifecycle automation prevents future drift.
---
author: oompah
created: 2026-07-31 10:35
---
Explicit operator rebase request: OOMPAH-652 is a merged safety prerequisite, but epic-OOMPAH-619 and preserved child branches OOMPAH-623/650 still predate commit ec0ec7d89 and retain the unsafe canonical PID-file test lifecycle. Rebase the shared epic onto current main through the normal bounded rebase workflow before either child resumes or runs a full gate.
---
author: oompah
created: 2026-07-31 14:49
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 14:49
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 14:49
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 15:00
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- epic_branch_head: 659a09ddc01b4afba181e274e9650e944850367b
- main_head: 8c75a201e328949d4057bfbd53e11cd5498ed72f
- epic_commits_ahead_of_main: 26
- main_commits_ahead_of_epic: 2
- auditor_worktree_head: 8c75a201e328949d4057bfbd53e11cd5498ed72f
- auditor_worktree_branch: OOMPAH-619
- children_status: OOMPAH-620/621/623/624/650/660/662 = Done
- resolver_module: oompah/client_auth.py (netrc + CLI + env + password-file precedence, embedded-URL rejection, TOCTOU-safe file reads)
- canonical_cli_sync_scripts: scripts/canonical_cli_cutover.py, scripts/sync_canonical_cli.py
- test_files_added_or_modified_on_epic: tests/test_client_auth.py, tests/test_task_handoff.py, tests/test_actor_mapping.py, tests/test_server_actor_binding.py, tests/test_task_cli_actor.py, tests/test_docs_authentication_contract.py, tests/test_cli_install_revision_compatibility.py, tests/test_canonical_cli_sync.py, tests/test_lifecycle_cli_sync_integration.py, tests/test_build_identity.py, tests/test_makefile_restart_wait.py, tests/test_oompah_http.py, tests/test_orchestrator_full_sync.py
- docs_updated: docs/authentication.md, docs/cli-install.md, docs/authentication-identity-mapping.md
- workflow_definition_of_done: Per docs/task-epic-workflow.md: Done = 'Work is complete, but may still be awaiting an epic rollup'; Done -> Merged transition is a separate phase
- task_labels_present: rebase-requested, epic:rebasing (retained; not gating Done per workflow but should be reconciled at Merged)
- note_on_operator_reinstall: Task description's 'operator will reinstall...after epic reaches main' is a Merged-phase verification, not a Done-phase gate
---
author: oompah
created: 2026-07-31 15:00
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 100, Tool calls: 77
- Tokens: 83 in / 24.7K out [24.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 10m 42s
- Log: OOMPAH-619__20260731T144953Z.jsonl
---
author: oompah
created: 2026-07-31 19:56
---
Rebased the completed epic onto main, preserving the owner-authority retry cancellation alongside the task-handoff permit changes. Removed the tracked generated hook symlink, normalized inherited whitespace, and pushed b55160d3798d228e140881d9d5bacbc0439cfc78. Verification: 213 focused tests passed; full make test passed with 14,534 passed, 7 skipped, 1 xfailed.
---
author: oompah
created: 2026-07-31 20:15
---
Hosted CI exposed two environment-budget regressions after the rebase: identity-safe Granian cleanup scanned host-wide procfs under a 5-second test timeout, and the isolated exact-revision pip install had a 120-second subprocess limit. Fixed at 34a612911 by walking only kernel-reported owned descendants, restoring direct child identity capture, adding a no-global-scan regression, and using a hosted-runner-safe install budget. Verification: 56 focused tests passed; full make test passed with 14,534 passed, 7 skipped, 1 xfailed.
---
author: oompah
created: 2026-07-31 20:36
---
A second hosted CI pass exposed two more boundedness bugs: the exact-revision test re-resolved dependencies for five minutes, and the free-port macro ran lsof after ss had already reported no listener. Fixed at 755797119 by installing only the pinned package against the already-installed dependency directory and making ss authoritative with lsof used only when ss is absent. Verification: 7 focused regressions passed; full make test passed with 14,535 passed, 7 skipped, 1 xfailed.
---
author: oompah
created: 2026-07-31 20:54
---
Final hosted-CI boundedness fix pushed at ba5e86c7e. The exact-revision CLI test now avoids redundant dependency installation and build isolation while preserving VCS revision metadata, lifecycle port checks use ss authoritatively instead of falling through to unbounded lsof scans, and hatchling is explicit in the dev environment. Focused hosted-failure reproductions: 6 passed. Complete branch gate: 14,535 passed, 7 skipped, 1 xfailed in 376.02s. PR #626 auto-merge remains armed; waiting for the fresh matrix on this exact head.
---
author: oompah
created: 2026-07-31 21:19
---
Hosted Python 3.11 exposed a final fixture-only boundedness defect: pip partial-cloned the local shallow exact-revision source by repeatedly lazy-fetching the same commit until the 120-second timeout. Commit b8658598d now constructs a one-revision 4-MiB VCS remote and makes pip use a normal clone for this fixture, while retaining a genuine VCS install and exact PEP 610 commit assertion. Focused compatibility file: 19 passed in 5.16s on the committed head. Complete branch gate: 14,535 passed, 7 skipped, 1 xfailed in 374.13s. Pushed for a fresh PR #626 matrix.
---
author: oompah
created: 2026-07-31 21:29
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 21:29
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 21:29
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 1
- Tokens: 12 in / 16 out [28 total]
- Cost: $0.0000
- Exit: terminated, Duration: 22s
- Log: OOMPAH-619__20260731T212906Z.jsonl
---
author: oompah
created: 2026-07-31 21:30
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-07-31 21:30
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 21:33
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- main_head: 16362384be835d1485d1121ce3c8329743391c79
- merge_commit_message: Merge pull request #626 from lesserevil/epic-OOMPAH-619
- worktree_head: 8c75a201e328949d4057bfbd53e11cd5498ed72f
- worktree_behind_main_by: 49 commits
- children_status: OOMPAH-620/621/623/624/650/660/662 = Done
- key_files_on_main: oompah/client_auth.py, scripts/canonical_cli_cutover.py, scripts/sync_canonical_cli.py, tests/test_client_auth.py, tests/test_canonical_cli_sync.py, tests/test_cli_install_revision_compatibility.py, tests/test_lifecycle_cli_sync_integration.py, tests/test_docs_authentication_contract.py
- docs_on_main: docs/authentication.md, docs/cli-install.md, docs/authentication-identity-mapping.md
- focused_tests_result: 62 passed (test_client_auth.py), 5 passed (test_docs_authentication_contract.py)
- full_gate_result: 14535 passed, 7 skipped, 1 xfailed (confirmed by multiple CI comments)
- pr_number: 626
- labels_present: rebase-requested, epic:rebasing (residual from completed rebase workflow)
- previous_done_audit: PASS by opus auditor, 2026-07-31 15:00
---
author: oompah
created: 2026-07-31 21:34
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 0, Tool calls: 26
- Tokens: 44 in / 1.4K out [1.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 31s
- Log: OOMPAH-619__20260731T213045Z.jsonl
---
author: oompah
created: 2026-08-07 21:54
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-07 21:54
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-07 22:35
---
Audit PASS — Archived

OOMPAH-619 Archived audit: PASS. Epic successfully merged into main (PR #626, commit 16362384b). All children marked Done. Current test results: 15962 passed, 7 skipped, 1 xfailed (serial gate). Epic delivers unified CLI authentication resolver with netrc/CLI/env/password-file precedence, comprehensive tests, and documentation.

Safe evidence:
- merge_commit: 16362384b
- pr_number: 626
- merge_verified: git merge-base --is-ancestor 16362384b HEAD returns 0
- test_results_serial: 15962 passed, 7 skipped, 1 xfailed (0 failures)
- test_results_previous: 14535 passed, 7 skipped, 1 xfailed (2026-07-31 21:33)
- children_status: OOMPAH-620/621/623/624/650/660/662 = Done
- key_files_on_main[0]: oompah/client_auth.py
- key_files_on_main[1]: scripts/canonical_cli_cutover.py
- docs_updated[0]: docs/authentication.md
- docs_updated[1]: docs/cli-install.md
- parallel_run_note: 4 SQLite timeout failures in parallel mode pass in serial mode
---
<!-- COMMENTS:END -->
