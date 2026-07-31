---
id: OOMPAH-619
type: epic
status: In Review
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
updated_at: '2026-07-31T21:19:57.052692Z'
work_branch: epic-OOMPAH-619
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/626
review_number: '626'
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-3a4b0536b50d: '2026-07-31T15:00:12.993955+00:00'
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
oompah.task_costs:
  total_input_tokens: 83
  total_output_tokens: 24712
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 83
      output_tokens: 24712
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 83
    output_tokens: 24712
    cost_usd: 0.0
    recorded_at: '2026-07-31T15:00:29.229888+00:00'
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
<!-- COMMENTS:END -->
