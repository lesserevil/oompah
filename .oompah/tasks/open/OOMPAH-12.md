---
id: OOMPAH-12
type: bug
status: Open
priority: 2
title: Expose labels and parent epic controls for native task creation
parent: null
children: []
blocked_by: []
labels:
- bug
- native-tracker
- ui
- task-creation
assignee: null
created_at: '2026-06-20T03:02:22.002875Z'
updated_at: '2026-06-20T03:36:11.945181Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

The dashboard create dialog still treats labels and parent-epic selection as GitHub-only. `isGitHubBacked(projectId)` returns true only for `tracker_kind === "github_issues"`, and the entire `create-github-fields` block is hidden for native `oompah_md` projects.

That is wrong after the native tracker cut-over:
- `POST /api/v1/issues` already accepts `labels` and `parent_id` for all tracker backends.
- `OompahMarkdownTracker.create_issue()` persists labels and parent metadata.
- Native projects need parent/child task creation and routing labels just as much as direct GitHub Issues projects.

Expected behavior:
- Parent Epic selection is available for native `oompah_md` projects when creating standalone tasks.
- Focus/routing labels are available for native `oompah_md` projects and are submitted as `labels`.
- GitHub-specific fields, if any, are separated from general oompah task metadata.

Acceptance criteria:
- Replace the overly broad `isGitHubBacked` gate with capability-specific helpers, e.g. supports labels, supports parent epic, supports target branch.
- Show and submit labels and parent epic for `oompah_md` and `github_issues` where supported.
- Keep genuinely GitHub-only behavior gated to direct GitHub-backed projects if still needed.
- Add dashboard tests proving native task creation includes labels and parent epic values.
- Do not regress GitHub Issues project creation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

