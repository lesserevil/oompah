---
id: OOMPAH-46
type: task
status: In Progress
priority: null
title: 'Maintainer: update workflow dispatch description to v1.0.0 examples (needs
  workflow PAT scope)'
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T02:11:02.984832Z'
updated_at: '2026-07-13T15:02:43.232975Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 019a5086-a6c6-4227-a18f-33918dbc0553
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
author: oompah
created: 2026-07-13 14:57
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-13 14:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 14:58
---
UNDERSTANDING: OOMPAH-46 is NOT a duplicate of OOMPAH-43. OOMPAH-43 was the original task but was Archived (not Done) because the PAT lacked 'workflow' scope to push .github/workflows/cli-release.yml. OOMPAH-46 was explicitly filed as a Needs Human follow-up. The user has now granted workflow PAT scope. Proceeding with: (1) update .github/workflows/cli-release.yml line 10 description from 'e.g. v0.1.0' to 'e.g. v1.0.0-draft or v1.0.0', (2) add test_release_workflow_dispatch_description_shows_v1_examples to tests/test_cli_release_packaging.py before test_release_workflow_is_tag_or_manual_github_release_only.
---
author: oompah
created: 2026-07-13 15:00
---
IMPLEMENTATION: Made two changes: (1) .github/workflows/cli-release.yml line 10: description changed from 'e.g. v0.1.0' to 'e.g. v1.0.0-draft or v1.0.0'. (2) Added test_release_workflow_dispatch_description_shows_v1_examples to tests/test_cli_release_packaging.py (inserted before test_release_workflow_is_tag_or_manual_github_release_only as specified). Running tests now.
---
author: oompah
created: 2026-07-13 15:02
---
VERIFICATION: All 12 tests in tests/test_cli_release_packaging.py pass, including the new test_release_workflow_dispatch_description_shows_v1_examples. Full suite: 7994 passed, 28 skipped. Committing and pushing.
---
<!-- COMMENTS:END -->
