---
id: OOMPAH-47
type: task
status: In Progress
priority: null
title: Add oompah project-bootstrap --help to cli-release.yml workflow smoke checks
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T02:35:48.855045Z'
updated_at: '2026-06-22T02:37:50.494336Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

OOMPAH-24 added 'oompah project-bootstrap --help' to the release smoke test docs and installed-CLI smoke tests, but could not update .github/workflows/cli-release.yml because the current PAT lacks workflow scope. A human or PAT with workflow scope needs to add this line after 'oompah task --help' in the smoke-install step of .github/workflows/cli-release.yml:\n\n  oompah project-bootstrap --help\n\nAlso add the corresponding assertion to test_release_workflow_is_tag_or_manual_github_release_only in tests/test_cli_release_packaging.py and update the description paragraph in docs/cli-release.md.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

