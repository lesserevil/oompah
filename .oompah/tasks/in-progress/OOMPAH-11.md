---
id: OOMPAH-11
type: bug
status: In Progress
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
updated_at: '2026-06-20T03:46:01.210736Z'
work_branch: OOMPAH-11
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/337
review_number: '337'
merged_at: null
oompah.agent_run_id: 22493232-7f76-45ae-b877-9a67c0a8d296
oompah.review_url: https://github.com/lesserevil/oompah/pull/337
oompah.review_number: '337'
oompah.work_branch: OOMPAH-11
oompah.target_branch: main
oompah.task_costs:
  total_input_tokens: 71
  total_output_tokens: 2100
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 71
      output_tokens: 2100
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 71
    output_tokens: 2100
    cost_usd: 0.0
    recorded_at: '2026-06-20T03:44:10.383022+00:00'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-20 03:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-20 03:37
---
Understanding: Investigating OOMPAH-11. No duplicate found among existing tasks. Issue: the three issue-template endpoints (status, preview, apply) guard with tracker_kind == 'github_issues' only, but native oompah_md projects with github_issue_intake_enabled=true should also be supported. Plan: (1) find the endpoint guards, (2) add a shared predicate, (3) update endpoints, (4) add regression tests, (5) update any UI test references.
---
author: oompah
created: 2026-06-20 03:38
---
Discovery: Found the root cause. In oompah/server.py, all three issue-template endpoints (status, preview, apply) guard with _is_github_tracker_kind() which only accepts tracker_kind='github_issues'. The fix is to add a new predicate _has_github_issue_template_capability() that also accepts oompah_md projects when github_issue_intake_enabled=True and tracker_owner/repo are configured. 4 test classes in tests/test_issue_template_refresh.py need updating: keep existing 400 for oompah_md-without-intake, add new passing cases for oompah_md+intake.
---
author: oompah
created: 2026-06-20 03:41
---
Implementation: Added _has_github_issue_template_capability() predicate in oompah/server.py that accepts: (1) github_issues tracker kind, OR (2) oompah_md with github_issue_intake_enabled=True + tracker_owner + tracker_repo configured. Updated all 3 issue-template endpoints (status, preview, apply) to use this predicate instead of _is_github_tracker_kind(). Improved error messages to mention github_issue_intake_enabled requirement. Added 8-test suite for the predicate + 9 regression tests covering oompah_md+intake for all 3 endpoints including dirty-worktree safety and missing-owner edge cases.
---
author: oompah
created: 2026-06-20 03:42
---
Verification: All 6923 tests pass (make test). Issue-template-specific suite: 51/51 passed. New tests confirm: oompah_md+intake=True+owner+repo → 200 for status/preview/apply; oompah_md without intake still returns 400; dirty-worktree safety preserved for native intake projects.
---
author: oompah
created: 2026-06-20 03:42
---
Completion: Delivered fix for OOMPAH-11. Added _has_github_issue_template_capability() predicate and updated all 3 issue-template API endpoints (status/preview/apply) to accept oompah_md projects with github_issue_intake_enabled=True + tracker_owner/repo configured. 51 issue-template tests pass, 6923 total tests pass. Branch OOMPAH-11 pushed.
---
author: oompah
created: 2026-06-20 03:44
---
Added _has_github_issue_template_capability() predicate; updated status/preview/apply endpoints to accept oompah_md+github_issue_intake_enabled=True projects; 17 new regression tests (8 predicate unit tests + 9 endpoint integration tests); all 6923 tests pass.
---
author: oompah
created: 2026-06-20 03:44
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 46
- Tokens: 71 in / 2.1K out [2.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 41s
- Log: OOMPAH-11__20260620T033635Z.jsonl
---
author: oompah
created: 2026-06-20 03:44
---
Review reconciliation reopened this task because it was marked In Review but no open review artifact exists.

No PR/MR for this branch was found.
Branch: `OOMPAH-11`
Target branch: `main`
Unmerged commits: 1 commit
  244ecc4 OOMPAH-11: Allow issue template refresh for native GitHub-intake projects

Required: restore or recreate the PR/MR for this branch, then move the task back to In Review after the review exists.
---
author: oompah
created: 2026-06-20 03:45
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-20 03:46
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
