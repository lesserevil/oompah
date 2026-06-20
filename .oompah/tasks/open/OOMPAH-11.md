---
id: OOMPAH-11
type: bug
status: Open
priority: 1
title: Allow issue template refresh for native GitHub-intake projects
parent: null
children: []
blocked_by: []
labels:
- bug
- native-tracker
- github-intake
- templates
assignee: null
created_at: '2026-06-20T03:02:09.918768Z'
updated_at: '2026-06-20T03:35:56.635941Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

The managed-project issue-template refresh workflow still rejects projects unless `tracker_kind` is `github_issues`. After the native tracker cut-over, the default project workflow is `oompah_md` plus optional `github_issue_intake_enabled`, and those projects still rely on GitHub issue forms as the external intake surface.

Current behavior:
- Projects page shows the Templates action for native projects.
- `/api/v1/projects/{id}/issue-templates/status`, `/preview`, and `/apply` return 400: issue template refresh is only available for github_issues projects.

Expected behavior:
- Template status/preview/apply should be available for `oompah_md` projects when `github_issue_intake_enabled=true` and the project has enough GitHub repo config to manage `.github/ISSUE_TEMPLATE`.
- Native projects without GitHub intake should still receive a clear not-applicable response.
- Error messages should refer to GitHub issue intake capability, not only direct `github_issues` tracker kind.

Acceptance criteria:
- Add a shared predicate for projects whose GitHub issue templates are applicable: direct `github_issues`, or native `oompah_md` with GitHub issue intake enabled and tracker owner/repo configured.
- Update all three issue-template endpoints to use that predicate.
- Update Projects UI/tests so the Templates action works for native intake projects and clearly explains non-applicable projects.
- Add regression tests covering `oompah_md + github_issue_intake_enabled=true` for status, preview, and apply.
- Preserve dirty-worktree safety and commit/push behavior.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

