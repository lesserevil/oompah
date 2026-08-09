---
id: OOMPAH-933
type: task
status: Backlog
priority: null
title: Make protected-main CI reproduce the supported quality gate
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T06:09:37.822614Z'
updated_at: '2026-08-09T06:09:37.822614Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Problem: required GitHub-hosted CI runs pytest directly without provisioning bubblewrap, a real project .venv, or Git commit identity. PR #749 therefore fails on all supported Python versions even though the exact Makefile gate passes locally: sandbox tests fail closed because bwrap is absent, nested run-tests rejects the missing .venv interpreter, and temporary Git commits lack identity. This makes protected main impossible to update. Scope: update .github/workflows/ci.yml to provision and smoke-test the OS sandbox, create the project test environment through Makefile targets, configure the canonical bot Git identity, and run the supported make test gate. Add static regression coverage for the hosted CI contract. Acceptance: focused workflow-contract tests pass; the exact local full gate passes; PR #749's required Python 3.11/3.12/3.13 checks pass without bypassing branch protection.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

