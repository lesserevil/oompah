---
id: OOMPAH-48
type: task
status: Backlog
priority: null
title: Apply workflow+test assertion for oompah project-bootstrap --help (needs workflow-scoped
  PAT)
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T02:46:23.693967Z'
updated_at: '2026-06-22T02:46:23.693967Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

OOMPAH-47 completed the docs/cli-release.md update but cannot push changes to .github/workflows/cli-release.yml (GitHub rejects pushes modifying workflow files without workflow scope on the PAT).\n\nA human or workflow-scoped PAT must apply and push these two changes together (they must be atomic — the test asserts the workflow file contains the line):\n\n**1. .github/workflows/cli-release.yml** — add 'oompah project-bootstrap --help' after 'oompah task --help' in the 'Verify wheel console script' step:\n\n```diff\n           oompah --help\n           oompah task --help\n+          oompah project-bootstrap --help\n```\n\n**2. tests/test_cli_release_packaging.py** — add assertion to test_release_workflow_is_tag_or_manual_github_release_only:\n\n```diff\n     assert "oompah --help" in text\n     assert "oompah task --help" in text\n+    assert "oompah project-bootstrap --help" in text\n     assert "gh release create" in text\n```\n\nThe changes are already staged as working-directory modifications on the OOMPAH-47 branch (git stash was popped). A maintainer with workflow scope can commit them directly to the OOMPAH-47 branch and push, or apply the patch manually to main.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

