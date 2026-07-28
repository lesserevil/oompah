---
id: OOMPAH-455
type: bug
status: Backlog
priority: 1
title: Make GitLab project edits use one intake alias and forge-aware identity resolution
parent: OOMPAH-451
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T12:34:53.400428Z'
updated_at: '2026-07-28T12:34:53.400428Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem: the Projects editor always sends both github_issue_intake_enabled and external_issue_intake_enabled. ProjectStore explicitly rejects both, so any edit, including enabling state_branch_enabled, fails with Specify only one error even when both values are false and equal. The same save path also calls the GitHub token-owner API when status_actor_login is blank, generating GitHub 401 warnings for a valid GitLab token.

Implementation scope: send one canonical forge-neutral intake field from oompah/templates/projects.html; make the PATCH compatibility contract deterministic for legacy and neutral clients; resolve actor identity with the configured forge provider or leave it unset without calling another forge. Ensure editing unrelated settings does not rewrite or validate unrelated aliases. Relevant files include oompah/templates/projects.html, oompah/server.py, oompah/projects.py, and project CRUD/GitLab UI tests.

Tests: reproduce editing a GitLab project with both stored intake aliases represented in the GET response, enable state_branch_enabled through the UI payload, assert a successful update, and assert no GitHub identity call; cover legacy GitHub clients and conflicting alias values explicitly; run make test.

Acceptance criteria: enabling the state branch for nodevirt succeeds from the Projects page; matching compatibility aliases never block unrelated edits; conflicting values receive a precise validation error; GitLab credentials are never sent to GitHub.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

