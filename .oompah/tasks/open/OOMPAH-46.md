---
id: OOMPAH-46
type: task
status: Open
priority: null
title: 'Maintainer: update workflow dispatch description to v1.0.0 examples (needs
  workflow PAT scope)'
parent: null
children: []
blocked_by: []
labels:
- needs:human
assignee: null
created_at: '2026-06-22T02:11:02.984832Z'
updated_at: '2026-07-13T14:57:16.207522Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

The lesserevil PAT lacks 'workflow' scope, blocking automated push of changes to .github/workflows/cli-release.yml. NVShawn has workflow scope but lacks push access to lesserevil/oompah.

EXACT CHANGE NEEDED (one-liner):
File: .github/workflows/cli-release.yml line 10

FROM:  description: "Existing release tag to package, e.g. v0.1.0"
TO:    description: "Existing release tag to package, e.g. v1.0.0-draft or v1.0.0"

ALSO ADD this test to tests/test_cli_release_packaging.py (before test_release_workflow_is_tag_or_manual_github_release_only):

def test_release_workflow_dispatch_description_shows_v1_examples():
    """Workflow dispatch description should hint at v1.0.0-draft and v1.0.0 forms."""
    text = WORKFLOW_PATH.read_text(encoding='utf-8')
    workflow = yaml.safe_load(text)
    dispatch = (workflow.get('on') or workflow.get(True))['workflow_dispatch']
    description = dispatch['inputs']['tag']['description']
    assert 'v1.0.0-draft' in description
    assert 'v1.0.0' in description

HOW TO PUSH:
A maintainer must create a PAT with 'repo' + 'workflow' scopes, or grant NVShawn push access to lesserevil/oompah, then push the two-file change on branch OOMPAH-43 or directly on main.

SOURCE: OOMPAH-43 (which was filed by OOMPAH-18 for the same reason).
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:11
---
Requires maintainer token with workflow scope to push .github/workflows/cli-release.yml
---
author: user
created: 2026-07-13 14:52
---
Workflow permissions added to PAT for this project. Please continue.
---
<!-- COMMENTS:END -->
