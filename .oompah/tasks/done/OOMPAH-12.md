---
id: OOMPAH-12
type: bug
status: Done
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
updated_at: '2026-06-20T04:03:19.017191Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 8848edba-d456-4293-a07e-0ace4be5914f
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-20 03:49
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-20 03:49
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-20 03:49
---
Understanding: Investigating OOMPAH-12 as Duplicate Investigator. The issue reports that the dashboard create dialog hides labels and parent-epic selection for native oompah_md projects because isGitHubBacked() only returns true for github_issues tracker_kind. The fix involves replacing isGitHubBacked with capability-specific helpers. Before implementing, I need to check if any prior task already covers this same problem.
---
author: oompah
created: 2026-06-20 03:56
---
Discovery: No duplicate found. This is a unique issue. All other tasks (OOMPAH-11: template refresh, OOMPAH-13: status actor, OOMPAH-14: webhook label normalization) address different problems. OOMPAH-12 specifically targets the dashboard create dialog where isGitHubBacked() gates ALL of: target branch, focus labels, and parent epic for oompah_md projects. Root cause confirmed in dashboard.html: updateGitHubFieldsVisibility() only shows create-github-fields (which wraps all three controls) when isGitHubBacked() is true. submitCreateDialog() also gates labels and parent_id dropdown on isGitHubBacked(). Plan: (1) Add supportsLabels() and supportsParentEpic() helpers returning true for oompah_md AND github_issues. (2) Separate HTML: move focus-labels and parent-epic into new create-tracker-fields div (shown for both), keep create-github-fields for target-branch-row only (GitHub-only). (3) Update updateGitHubFieldsVisibility() to use the new helpers. (4) Update submitCreateDialog() to gate labels/parent_epic on supportsLabels/supportsParentEpic. (5) Add tests/test_dashboard_create_native.py with tests for native task creation including labels and parent epic.
---
author: oompah
created: 2026-06-20 04:02
---
Implementation: Modified oompah/templates/dashboard.html and added tests/test_dashboard_create_native.py. Changes: (1) Added supportsLabels() and supportsParentEpic() helpers that return true for both oompah_md and github_issues tracker kinds. (2) Restructured HTML: focus-labels-row and parent-epic-row moved from create-github-fields into new create-tracker-fields div (shown for all supported trackers). create-github-fields now contains only the target-branch-row (GitHub-only). (3) Updated updateGitHubFieldsVisibility() to show create-tracker-fields via supportsLabels() and create-github-fields via isGitHubBacked(). (4) Updated submitCreateDialog() to gate labels/parent_epic on supportsLabels()/supportsParentEpic() instead of isGitHubBacked(). (5) Added CSS for #create-tracker-fields. (6) Added 31 new tests in test_dashboard_create_native.py covering supportsLabels/supportsParentEpic, HTML structure, visibility logic, and native task creation including labels and parent epic. All 6937 tests pass (was 6923 before).
---
author: oompah
created: 2026-06-20 04:02
---
Verification: All 6937 tests pass (28 skipped). New tests/test_dashboard_create_native.py: 31/31 passed. Existing tests/test_dashboard_create_github.py: 34/34 passed (no regressions on GitHub Issues behavior). New test classes cover: TestSupportsLabels (6 tests), TestSupportsParentEpic (6 tests), TestCreateTrackerFieldsHTML (6 tests), TestUpdateFieldsVisibilityNative (5 tests), TestSubmitCreateDialogNative (7 tests). Key verifications: supportsLabels/supportsParentEpic accept oompah_md AND github_issues; create-tracker-fields div exists and is hidden by default; focus-labels and parent-epic are inside create-tracker-fields (not github-only); target-branch stays inside create-github-fields (GitHub-only); submitCreateDialog uses supportsLabels/supportsParentEpic for labels and parent_epic fields.
---
author: oompah
created: 2026-06-20 04:02
---
Completion: Duplicate investigation confirmed no prior task covers this specific bug. Delivered fix for OOMPAH-12. Changes to oompah/templates/dashboard.html: added supportsLabels() and supportsParentEpic() capability-specific helpers (true for oompah_md + github_issues), restructured HTML so focus-labels and parent-epic live in new create-tracker-fields div (shown for all supported trackers), target-branch stays in create-github-fields (GitHub-only), updated updateGitHubFieldsVisibility() and submitCreateDialog() to use the new helpers. Added tests/test_dashboard_create_native.py (31 new tests). All 6937 tests pass. Branch OOMPAH-12 pushed to origin.
---
author: oompah
created: 2026-06-20 04:03
---
Added supportsLabels() and supportsParentEpic() helpers for oompah_md+github_issues; restructured create dialog HTML so focus labels and parent epic show for native projects; 31 new tests; all 6937 tests pass; no GitHub Issues regression.
---
author: oompah
created: 2026-06-20 04:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 42
- Tokens: 72 in / 1.6K out [1.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 14m 2s
- Log: OOMPAH-12__20260620T034937Z.jsonl
---
<!-- COMMENTS:END -->
