---
id: OOMPAH-619
type: epic
status: In Validation
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
updated_at: '2026-07-31T14:49:51.452135Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-3b0770c606df
    project_id: proj-14849f1b
    task_id: OOMPAH-619
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a0a813b257073a0b1699ed144144a8a44b89e75cd90141bd2f0965d3fcfbb03a
    attempts:
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
    requested_by:
      version: 1
      identity: orchestrator
    previous_state: Open
    created_at: '2026-07-31T14:49:39.308179+00:00'
    updated_at: '2026-07-31T14:49:46.247336+00:00'
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
<!-- COMMENTS:END -->
