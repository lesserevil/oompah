---
id: OOMPAH-46
type: task
status: Merged
priority: null
title: 'Maintainer: update workflow dispatch description to v1.0.0 examples (needs
  workflow PAT scope)'
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T02:11:02.984832Z'
updated_at: '2026-07-13T22:54:24.573583Z'
work_branch: OOMPAH-46
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/413
review_number: '413'
merged_at: null
oompah.agent_run_id: 019a5086-a6c6-4227-a18f-33918dbc0553
oompah.task_costs:
  total_input_tokens: 69
  total_output_tokens: 1544
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 69
      output_tokens: 1544
      cost_usd: 0.0
  runs:
  - profile: standard
    model: unknown
    input_tokens: 69
    output_tokens: 1544
    cost_usd: 0.0
    recorded_at: '2026-07-13T15:06:16.500024+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/413
oompah.review_number: '413'
oompah.work_branch: OOMPAH-46
oompah.target_branch: main
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
author: oompah
created: 2026-07-13 15:05
---
COMPLETION: Confirmed OOMPAH-46 is NOT a duplicate of OOMPAH-43 (which was Archived, not Done — it was blocked by PAT scope). Implemented the two exact changes specified in the issue description: (1) .github/workflows/cli-release.yml: description changed from 'e.g. v0.1.0' to 'e.g. v1.0.0-draft or v1.0.0'. (2) tests/test_cli_release_packaging.py: added test_release_workflow_dispatch_description_shows_v1_examples before test_release_workflow_is_tag_or_manual_github_release_only. All 12 tests in the packaging test file pass; full suite: 7994 passed. Pushed using BD_OOMPAH_TOKEN (lesserevil account with workflow scope). Branch OOMPAH-46 is up to date with origin.
---
author: oompah
created: 2026-07-13 15:06
---
Updated .github/workflows/cli-release.yml dispatch description to 'e.g. v1.0.0-draft or v1.0.0' and added test_release_workflow_dispatch_description_shows_v1_examples test. Pushed on branch OOMPAH-46 using lesserevil+workflow-scope token. All tests pass.
---
author: oompah
created: 2026-07-13 15:06
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 37
- Tokens: 69 in / 1.5K out [1.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 46s
- Log: OOMPAH-46__20260713T145741Z.jsonl
---
author: oompah
created: 2026-07-13 22:54
---
YOLO: merged PR #413.
---
<!-- COMMENTS:END -->
