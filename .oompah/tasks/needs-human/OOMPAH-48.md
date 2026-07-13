---
id: OOMPAH-48
type: task
status: Needs Human
priority: null
title: Apply workflow+test assertion for oompah project-bootstrap --help (needs workflow-scoped
  PAT)
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T02:46:23.693967Z'
updated_at: '2026-07-13T14:56:31.438415Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

OOMPAH-47 completed the docs/cli-release.md update but cannot push changes to .github/workflows/cli-release.yml (GitHub rejects pushes modifying workflow files without workflow scope on the PAT).

A human or workflow-scoped PAT must apply and push these two changes together (they must be atomic — the test asserts the workflow file contains the line):

**1. .github/workflows/cli-release.yml** — add 'oompah project-bootstrap --help' after 'oompah task --help' in the 'Verify wheel console script' step:

```diff
           oompah --help
           oompah task --help
+          oompah project-bootstrap --help
```

**2. tests/test_cli_release_packaging.py** — add assertion to test_release_workflow_is_tag_or_manual_github_release_only:

```diff
     assert "oompah --help" in text
     assert "oompah task --help" in text
+    assert "oompah project-bootstrap --help" in text
     assert "gh release create" in text
```

The changes are already staged as working-directory modifications on the OOMPAH-47 branch (git stash was popped). A maintainer with workflow scope can commit them directly to the OOMPAH-47 branch and push, or apply the patch manually to main.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:48
---
Needs workflow-scoped PAT to push workflow file changes
---
<!-- COMMENTS:END -->
