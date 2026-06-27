---
id: OOMPAH-158
type: bug
status: In Progress
priority: null
title: Make GitHub intake import parsing tolerant of Markdown issue bodies
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-26T22:14:16.817361Z'
updated_at: '2026-06-27T03:35:37.023283Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d235d15f-5aac-41e6-88ea-173e7fae4689
---
## Summary

GitHub issue intake should preserve and parse structured Markdown issue bodies so imported tasks expose a non-empty description and required-field validation sees Summary, work details, and acceptance criteria content.
## Problem
GitHub issue intake can import a well-structured GitHub issue into a native oompah task, but the resulting task/detail API may expose a null or empty normalized description and stale intake metadata that incorrectly marks required fields as missing.

Observed example: NVIDIA-Omniverse/trickle#268 imports as TRICKLE-8. The GitHub issue body includes a Summary, required quiet-install behavior, Acceptance criteria, and Notes. Direct validation of both the GitHub body and the imported markdown body passes, but TRICKLE-8 remains Proposed with intake missing_fields: acceptance_criteria, problem_statement, work_description, and the detail API reports description: null.

## Steps to Reproduce
1. Enable GitHub issue intake for the trickle project.
2. Import GitHub issue NVIDIA-Omniverse/trickle#268.
3. Inspect TRICKLE-8 in the dashboard or via /api/v1/issues/TRICKLE-8/detail?project_id=proj-3e4e9214.
4. Compare the intake summary with the original GitHub issue body.

## Actual Behavior
The imported task is marked as missing acceptance_criteria, problem_statement, and work_description even though the GitHub issue body contains those sections/content. The dashboard/detail API shows description as null, making the intake UI misleading.

## Expected Behavior
GitHub intake import should preserve and parse Markdown issue bodies robustly enough that validation sees the user-provided Summary/problem, work description, and acceptance criteria. If the imported body is structurally wrapped, validation should still inspect the meaningful original content rather than treating the description as empty.

## Acceptance Criteria
- GitHub issue intake preserves imported Markdown bodies so the native task detail API exposes a non-null description or otherwise provides the validator with the original content.
- Intake validation for an issue shaped like NVIDIA-Omniverse/trickle#268 does not incorrectly report acceptance_criteria, problem_statement, or work_description as missing.
- Existing imported tasks can be revalidated or corrected when their stored body already contains the required information.
- Regression tests cover a GitHub issue body with Summary, behavior/work-description bullets, Acceptance criteria, and Notes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-27 03:20
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-06-27 03:21
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-27 03:22
---
Understanding: OOMPAH-158 is NOT a duplicate. Searched all merged and archived tasks for related topics (intake validation, Markdown parsing, GitHub import body parsing, description null, missing_fields). Closest candidates OOMPAH-15 (auto-generated tasks failing intake) and OOMPAH-11 (issue template refresh) both address different problems. No existing task covers the bug where GitHub issue intake imports a well-structured Markdown body but the native task ends up with null description and the intake validator incorrectly reports acceptance_criteria/problem_statement/work_description as missing. Plan: (1) explore github_intake_bridge.py and related files to understand how the GitHub issue body is stored during import, (2) find the intake validator to see how it reads the body, (3) identify the root cause (body not being stored, or validator not reading it correctly), (4) implement a fix with regression tests.
---
author: oompah
created: 2026-06-27 03:30
---
Discovery: Root cause identified. When a GitHub issue body contains H2 Markdown headings (## Summary, ## Acceptance Criteria, etc.), the native_description_for_github_issue function embeds them in the native task's ## Summary section. The oompah_md_tracker._section() regex uses (?=^##\s+|\Z) as lookahead to stop at the next H2 heading. When the GitHub body starts with ## Summary, the outer ## Summary section body is EMPTY (the regex sees the inner ## Summary immediately). So issue.description = None. The orchestrator then runs validate_issue(description=None) on the proposed native task, which correctly reports all fields as missing, and _update_intake_metadata writes those to oompah.intake. Fix: in _native_description_for_github_issue, downgrade H1/H2 headings in the GitHub body to H3+ before embedding. The validator's _section_re matches #{1,6} (H1-H6) so it still finds ### Acceptance Criteria etc. The _section() regex only stops at ^##\s+ so H3+ headings don't break the Summary section boundary. Two files to change: github_intake_bridge.py (add heading demotion), tests/test_github_intake_bridge.py (add regression test).
---
author: oompah
created: 2026-06-27 03:35
---
Implementation: Fixed in oompah/github_intake_bridge.py. Added _demote_h1_h2_headings(body) helper that uses re.sub with ^(#{1,2})\s+(.+)$ to convert H1/H2 headings to H3+. Modified _native_description_for_github_issue to apply heading demotion before embedding the GitHub body in the native task's ## Summary section. Added 13 regression tests in TestDemoteH1H2Headings and TestNativeDescriptionMarkdownBody covering: unit tests for _demote_h1_h2_headings (H1/H2 demoted, H3+ unchanged, empty string, mixed), end-to-end that _section(body, 'Summary') returns non-null when GitHub body has ## headings, and that validate_issue passes for the demoted content. The fix is backward-compatible: GitHub bodies without H2 headings are passed through unchanged.
---
<!-- COMMENTS:END -->
