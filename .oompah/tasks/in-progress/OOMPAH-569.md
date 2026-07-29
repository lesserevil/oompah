---
id: OOMPAH-569
type: task
status: In Progress
priority: null
title: Sanitize credentials from branch quality-gate subprocesses
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T23:26:15.028867Z'
updated_at: '2026-07-29T23:26:20.329566Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: update BranchQualityGate so configured review and integration commands inherit a sanitized environment with OOMPAH_SERVER_USERNAME, OOMPAH_SERVER_PASSWORD, and OOMPAH_SERVER_PASSWORD_FILE removed, reusing the existing client_auth.agent_environment helper. This prevents server operator credentials from leaking into test/build subprocesses and removes the deterministic tests/test_client_auth.py failure seen in fresh integration worktrees. Relevant files: oompah/quality_gate.py and tests/test_quality_gate.py. Tests: add a regression command that records whether all client-auth variables are absent even when the parent process defines them; run focused quality-gate/client-auth tests and make test. Acceptance criteria: quality gates receive ordinary environment settings but no client auth secrets, the regression fails on the old behavior and passes with the fix, and the complete branch gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

