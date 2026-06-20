---
id: OOMPAH-7
type: task
status: Done
priority: null
title: Add GitHub-only CLI release packaging
parent: null
children: []
blocked_by: []
labels:
- external:github
assignee: null
created_at: '2026-06-20T02:13:20.705105Z'
updated_at: '2026-06-20T02:14:02.586115Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#313
  owner: lesserevil
  repo: oompah
  number: '313'
  url: https://github.com/lesserevil/oompah/issues/313
  requestor_login: lesserevil
  imported_comment_ids: []
  last_synced_status: Done
  last_synced_at: '2026-06-20T02:13:20.708080Z'
  migrated_at: '2026-06-20T02:13:20.708086Z'
  migrated_from_tracker: github_issues
  external_state: open
  external_created_at: '2026-06-15T02:39:03Z'
  external_updated_at: '2026-06-15T05:19:19Z'
  external_parent_id: lesserevil/oompah#312
---
## Summary

Create a repeatable release path for the oompah CLI that publishes artifacts through GitHub Releases only.

Implementation notes:
- build wheel/sdist artifacts from the tagged source state
- attach artifacts to GitHub Releases
- do not add PyPI publishing, PyPI tokens, or twine upload steps
- document how maintainers create and verify a CLI release tag

Acceptance criteria:
- release automation produces installable artifacts for the existing oompah console script
- the workflow is manual/tag-driven and cannot accidentally upload to PyPI
- release notes or generated output include the exact uv tool and pipx install commands for the tag or artifact

## External GitHub Issue
- URL: https://github.com/lesserevil/oompah/issues/313
- Requestor: @lesserevil
- Reference: lesserevil/oompah#313

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

