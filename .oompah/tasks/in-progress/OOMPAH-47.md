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
updated_at: '2026-06-22T02:48:25.935706Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 4cce9261-da8f-48f3-a004-4d646b751322
---
## Summary

OOMPAH-24 added 'oompah project-bootstrap --help' to the release smoke test docs and installed-CLI smoke tests, but could not update .github/workflows/cli-release.yml because the current PAT lacks workflow scope. A human or PAT with workflow scope needs to add this line after 'oompah task --help' in the smoke-install step of .github/workflows/cli-release.yml:\n\n  oompah project-bootstrap --help\n\nAlso add the corresponding assertion to test_release_workflow_is_tag_or_manual_github_release_only in tests/test_cli_release_packaging.py and update the description paragraph in docs/cli-release.md.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:37
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 02:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:38
---
UNDERSTANDING: This is NOT a duplicate. OOMPAH-24 was the original task that expanded smoke tests for project-bootstrap but explicitly could not update .github/workflows/cli-release.yml due to PAT scope limitations. OOMPAH-47 is the explicitly-created follow-up to complete that remaining work. 

Plan:
1. Add 'oompah project-bootstrap --help' after 'oompah task --help' in .github/workflows/cli-release.yml (Verify wheel console script step)
2. Add assertion 'assert "oompah project-bootstrap --help" in text' to test_release_workflow_is_tag_or_manual_github_release_only in tests/test_cli_release_packaging.py
3. Update the description paragraph in docs/cli-release.md to include 'oompah project-bootstrap --help' in both the workflow description and the manual verification section
---
author: oompah
created: 2026-06-22 02:38
---
DISCOVERY & IMPLEMENTATION: Three files modified:
1. .github/workflows/cli-release.yml — added 'oompah project-bootstrap --help' after 'oompah task --help' in the 'Verify wheel console script' step
2. tests/test_cli_release_packaging.py — added assertion 'assert "oompah project-bootstrap --help" in text' to test_release_workflow_is_tag_or_manual_github_release_only
3. docs/cli-release.md — updated workflow description paragraph and manual verification section to include 'oompah project-bootstrap --help'
---
author: oompah
created: 2026-06-22 02:48
---
VERIFICATION: Tests pass (7039 passed, 28 skipped). docs/cli-release.md change pushed to OOMPAH-47 branch.

The workflow file (.github/workflows/cli-release.yml) + corresponding test assertion changes cannot be pushed due to PAT workflow scope restriction — same issue as OOMPAH-24. These two changes (which must go together) are tracked in OOMPAH-48 (Needs Human).

Exact diff ready to apply:
- .github/workflows/cli-release.yml: add 'oompah project-bootstrap --help' after 'oompah task --help'
- tests/test_cli_release_packaging.py: assert 'oompah project-bootstrap --help' in workflow text

Changes remain as working-directory modifications on the OOMPAH-47 branch.
---
author: oompah
created: 2026-06-22 02:48
---
COMPLETION: 
- docs/cli-release.md: updated to include 'oompah project-bootstrap --help' in both the workflow description paragraph and the manual verification section — committed and pushed to OOMPAH-47 branch.
- .github/workflows/cli-release.yml + test assertion: both changes are prepared but require a workflow-scoped PAT to push. Tracked in OOMPAH-48 (Needs Human). The changes are confirmed correct and all tests pass with the full set of changes applied locally.
---
<!-- COMMENTS:END -->
