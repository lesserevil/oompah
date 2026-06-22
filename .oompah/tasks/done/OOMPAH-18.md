---
id: OOMPAH-18
type: task
status: Done
priority: 1
title: Update release docs, tests, and workflow examples for 1.0
parent: OOMPAH-17
children: []
blocked_by: []
labels:
- release:1.0
assignee: null
created_at: '2026-06-22T01:14:52.001843Z'
updated_at: '2026-06-22T01:53:19.760306Z'
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
author: oompah
created: 2026-06-22 01:52
---
IMPLEMENTATION: Updated 4 files for 1.0 convention. (1) docs/cli-release.md: replaced all v0.1.0 examples with v1.0.0 and added 1.0 release train section documenting release/1.0 branch, v1.0.0-draft (force-movable) and v1.0.0 (immutable) tags with separate draft vs. final release procedures. (2) docs/cli-install.md: replaced v0.1.0 examples with v1.0.0 in tag and wheel install commands. (3) tests/test_cli_release_packaging.py: updated test_release_notes_include_exact_tag_and_artifact_install_commands to use v1.0.0; updated test_release_docs_cover_tag_creation_and_verification_commands to assert v1.0.0; added test_release_docs_describe_draft_and_final_tag_convention (checks docs mention release/1.0, v1.0.0-draft, force-movable, immutable); added test_release_workflow_accepts_any_version_tag. (4) .github/workflows/cli-release.yml: workflow dispatch description update deferred to a maintainer (PAT lacks workflow scope) — file reverted, test updated to check v* wildcard instead.
---
author: oompah
created: 2026-06-22 01:52
---
VERIFICATION: All 8 tests in tests/test_cli_release_packaging.py pass (8 passed, 0 failed). Pre-existing failures in other test files are unrelated to this change. The workflow dispatch description (v0.1.0 → v1.0.0-draft or v1.0.0) cannot be updated in this branch due to PAT lacking workflow scope — this is a minor cosmetic hint string. A follow-up task will be filed.
---
author: oompah
created: 2026-06-22 01:53
---
COMPLETION: Delivered 1.0 convention updates across docs and tests. docs/cli-release.md now documents the 1.0 release train (release/1.0 branch, v1.0.0-draft draft tag, v1.0.0 final tag) with draft and final release procedures; all examples use v1.0.0. docs/cli-install.md examples updated to v1.0.0. tests/test_cli_release_packaging.py updated to assert 1.0 examples and two new tests added. Minor follow-up OOMPAH-43 filed for the workflow dispatch description update that requires maintainer workflow scope.
---
<!-- COMMENTS:END -->
