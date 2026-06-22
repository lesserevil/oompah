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
updated_at: '2026-06-22T02:38:58.201069Z'
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
<!-- COMMENTS:END -->
