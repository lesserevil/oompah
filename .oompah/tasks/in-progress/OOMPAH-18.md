---
id: OOMPAH-18
type: task
status: In Progress
priority: 1
title: Update release docs, tests, and workflow examples for 1.0
parent: OOMPAH-17
children: []
blocked_by: []
labels:
- release:1.0
assignee: null
created_at: '2026-06-22T01:14:52.001843Z'
updated_at: '2026-06-22T01:38:20.847137Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 658f04cf-f175-4257-b488-fbc726931f1b
---
## Summary

Plan: plans/oompah-1.0-release.md#epic-a-define-and-harden-the-10-release-train

WHAT TO DO
Update release documentation, release tests, and workflow examples from the current 0.1.0 examples to the 1.0 convention.

EXPECTED FORMAT
- release/1.0 branch
- v1.0.0-draft draft tag
- v1.0.0 final tag
- project.version = 1.0.0 on the release branch

HOW TO VERIFY
Docs and tests reference the 1.0 convention consistently and no 0.1.0 examples remain in release instructions except historical notes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 01:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 01:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 01:38
---
UNDERSTANDING: This is NOT a duplicate. OOMPAH-18 is a unique child of epic OOMPAH-17 with specific scope: update docs, tests, and workflow examples from 0.1.0 to 1.0 convention (release/1.0 branch, v1.0.0-draft draft tag, v1.0.0 final tag). No existing merged or done task covers this work. Proceeding to implement. Files to update: docs/cli-release.md (v0.1.0 → v1.0.0 throughout + add draft-tag workflow), docs/cli-install.md (v0.1.0 → v1.0.0), .github/workflows/cli-release.yml (dispatch description), tests/test_cli_release_packaging.py (assertions updated to 1.0 examples + new draft-tag coverage test).
---
author: oompah
created: 2026-06-22 01:38
---
DISCOVERY: Key files identified. docs/cli-release.md has v0.1.0 in all examples (tag creation, verify URL, uv/pipx install commands). docs/cli-install.md has v0.1.0 in tag and wheel install examples. .github/workflows/cli-release.yml uses 'e.g. v0.1.0' in dispatch description. tests/test_cli_release_packaging.py has two functions with 0.1.0: test_release_notes_include_exact_tag_and_artifact_install_commands (tests renderer with v0.1.0) and test_release_docs_cover_tag_creation_and_verification_commands (asserts docs contain v0.1.0). No tests yet cover the v1.0.0-draft draft-tag convention or the release/1.0 branch. Plan: update all examples to v1.0.0, add draft-tag workflow to cli-release.md, add draft-tag coverage to tests.
---
<!-- COMMENTS:END -->
