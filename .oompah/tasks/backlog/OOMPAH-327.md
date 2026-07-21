---
id: OOMPAH-327
type: task
status: Backlog
priority: 2
title: Expose GitLab configuration and health in UI, API, and ACP tools
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-319
- OOMPAH-323
- OOMPAH-325
labels: []
assignee: null
created_at: '2026-07-21T20:34:41.130372Z'
updated_at: '2026-07-21T20:35:19.837318Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, Webhooks, UI, bootstrap, and operations.

Extend project create/update/detail REST APIs, Projects UI, task CLI-compatible project payloads, and ACP project tools for forge_kind, forge_base_url, GitLab tracker/intake settings, masked project token, public webhook endpoint, hook health, and pipeline capability warnings. Keep old GitHub fields accepted and rendered correctly. Use “Merge Request” wording only when the project forge is GitLab.

Tests:
- API request/response compatibility for legacy GitHub payloads and GitLab payloads.
- UI DOM/JavaScript contract tests for conditional controls, token masking, validation errors, and hook-health display.
- ACP schema/list/create/update contract tests.

Acceptance criteria:
- Operators can configure and diagnose a GitLab project entirely through Oompah interfaces.
- GitHub project UI/API behavior is unchanged.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

