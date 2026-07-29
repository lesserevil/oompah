---
id: OOMPAH-569
type: task
status: Merged
priority: null
title: Sanitize credentials from branch quality-gate subprocesses
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T23:26:15.028867Z'
updated_at: '2026-07-29T23:41:25.372299Z'
work_branch: OOMPAH-569
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/585
review_number: '585'
merged_at: null
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: OOMPAH-569
  head_sha: 52619c962f88860534bdc858e79728e6f12db606
  submitted_at: '2026-07-29T23:34:16.246990+00:00'
  updated_at: '2026-07-29T23:34:16.246990+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/585
oompah.review_number: '585'
oompah.work_branch: OOMPAH-569
oompah.target_branch: main
---
## Summary

Implementation scope: update BranchQualityGate so configured review and integration commands inherit a sanitized environment with OOMPAH_SERVER_USERNAME, OOMPAH_SERVER_PASSWORD, and OOMPAH_SERVER_PASSWORD_FILE removed, reusing the existing client_auth.agent_environment helper. This prevents server operator credentials from leaking into test/build subprocesses and removes the deterministic tests/test_client_auth.py failure seen in fresh integration worktrees. Relevant files: oompah/quality_gate.py and tests/test_quality_gate.py. Tests: add a regression command that records whether all client-auth variables are absent even when the parent process defines them; run focused quality-gate/client-auth tests and make test. Acceptance criteria: quality gates receive ordinary environment settings but no client auth secrets, the regression fails on the old behavior and passes with the fix, and the complete branch gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 23:34
---
Sanitized branch quality-gate subprocess environments and versioned cached evidence so pre-fix failures rerun. Complete gate: 13,602 passed, 7 skipped.
---
<!-- COMMENTS:END -->
