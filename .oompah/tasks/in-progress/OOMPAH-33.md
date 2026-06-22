---
id: OOMPAH-33
type: task
status: In Progress
priority: 1
title: Refresh install and release docs for v1.0.0
parent: OOMPAH-32
children: []
blocked_by:
- OOMPAH-21
- OOMPAH-26
labels: []
assignee: null
created_at: '2026-06-22T01:17:15.169120Z'
updated_at: '2026-06-22T03:02:08.368523Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 76b95f93-03b2-43bc-912d-c5d563ec4fc3
---
## Summary

Plan: plans/oompah-1.0-release.md#operator-and-project-documentation

WHAT TO DO
Refresh install and release docs for the GitHub-only 1.0 release path, including Git tag installs and GitHub Release wheel installs.

HOW TO VERIFY
Docs use v1.0.0 and v1.0.0-draft examples where appropriate and do not describe PyPI publishing.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:58
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 02:58
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:59
---
UNDERSTANDING: Confirmed NOT a duplicate. OOMPAH-18 (plan A1: update docs/tests from 0.1.0 to 1.0 convention) is Done but its changes are not yet on main — docs/cli-install.md and docs/cli-release.md still show v0.1.0. OOMPAH-33 is plan D1 (Refresh install and release docs for GitHub-only 1.0 release), a child of the operator docs epic OOMPAH-32. Work: update both install and release docs to use v1.0.0 / v1.0.0-draft examples, ensure no PyPI publishing instructions remain, ensure both Git tag and GitHub Release wheel install paths are documented.
---
author: oompah
created: 2026-06-22 03:00
---
DISCOVERY: docs/cli-release.md and docs/cli-install.md both still use v0.1.0 examples throughout. tests/test_cli_release_packaging.py asserts for v0.1.0 in the docs. OOMPAH-18 did the same work on a separate branch that was never merged to main. Plan: (1) update docs/cli-release.md to v1.0.0 examples + add 1.0 release train section (release/1.0 branch, v1.0.0-draft draft tag, v1.0.0 final tag), (2) update docs/cli-install.md to v1.0.0 examples + note v1.0.0-draft, (3) update test assertions to match v1.0.0 and add test for draft/final convention.
---
author: oompah
created: 2026-06-22 03:02
---
IMPLEMENTATION: Updated 3 files. (1) docs/cli-release.md: replaced all v0.1.0 examples with v1.0.0; added '1.0 Release Train' section documenting release/1.0 branch, force-movable v1.0.0-draft draft tag, and immutable v1.0.0 final tag with separate draft vs. final release procedures. (2) docs/cli-install.md: replaced v0.1.0 with v1.0.0 in all tag and wheel install examples; added v1.0.0-draft install example with note about force-movable nature. Both docs already stated 'GitHub only — no PyPI release'. (3) tests/test_cli_release_packaging.py: updated test_release_notes_include_exact_tag_and_artifact_install_commands and test_release_docs_cover_tag_creation_and_verification_commands to assert v1.0.0; added test_release_docs_describe_draft_and_final_tag_convention; added test_install_docs_cover_tag_and_wheel_installs_for_v1.
---
<!-- COMMENTS:END -->
