---
id: OOMPAH-619
type: epic
status: Needs Rebase
priority: 1
title: Unify CLI authentication sources and align the installed client
parent: null
children:
- OOMPAH-620
- OOMPAH-621
- OOMPAH-623
- OOMPAH-624
- OOMPAH-650
blocked_by: []
start_blocked_by: []
labels:
- epic:stale
- rebase-requested
assignee: null
created_at: '2026-07-30T21:24:41.452666Z'
updated_at: '2026-07-31T10:40:16.356212Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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
<!-- COMMENTS:END -->
