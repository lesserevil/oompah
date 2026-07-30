---
id: OOMPAH-621
type: task
status: Backlog
priority: 1
title: Document and integration-test CLI credential precedence
parent: OOMPAH-619
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:25:29.809048Z'
updated_at: '2026-07-30T21:25:29.809048Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: update the user-facing authentication and CLI installation guides plus environment reference for direct CLI credentials, environment credentials, default user netrc discovery, exact precedence, hostname selection, and secure usage. Clearly state that command-line passwords are process-visible and recommend netrc or a mode-0600 password file for unattended operation. Add documentation contract and parser/help tests that keep task and admin surfaces aligned, ensure examples contain placeholders only, and verify password redaction. Add an end-to-end compatibility check that installs the standalone task CLI from an exact git revision in an isolated environment and authenticates it against the matching server revision through both task view and a safe admin read operation. Relevant files include docs/authentication.md, docs/cli-install.md, .env.example, tests/test_docs_authentication_contract.py, and CLI packaging/install tests. Begin from the integrated credential resolver behavior rather than inventing a second precedence contract. Acceptance criteria: operator docs and help agree exactly with implementation; examples cover argv, environment, password-file, and default netrc; install-from-revision compatibility is automated; focused documentation and packaging tests plus the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

