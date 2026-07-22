---
id: OOMPAH-328
type: task
status: In Progress
priority: 2
title: Make project bootstrap and operator documentation forge-aware
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-323
- OOMPAH-325
- OOMPAH-327
labels: []
assignee: null
created_at: '2026-07-21T20:34:42.051489Z'
updated_at: '2026-07-22T06:34:56.303462Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 1977dd7b-c132-46f1-92b0-53441edd738a
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, Webhooks, UI, bootstrap, and operations.

Extend project-bootstrap, readiness checks, templates, and operator documentation for GitLab.com and GitLab 17+ self-managed projects. Validate token/API access, label creation, issue tracker access, MR access, pipeline read access, state-branch push access, public HTTPS webhook URL, hook creation, and polling fallback. Document minimum GitLab token scopes, direct public webhook deployment, ordinary auto-merge semantics, merge-train non-support, recovery procedures, and GitHub compatibility.

Tests:
- Bootstrap dry-run fixtures for success plus each capability failure.
- Documentation contract tests for required GitLab configuration and security guidance.
- Existing GitHub bootstrap/readiness tests remain green.

Acceptance criteria:
- An operator can bootstrap a GitLab project without undocumented manual steps.
- Failure output identifies the exact missing capability and remediation.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 06:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 06:34
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
