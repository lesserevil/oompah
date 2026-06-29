---
id: OOMPAH-159
type: feature
status: Done
priority: null
title: Normalize Proposed task bodies during intake validation
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-29T14:14:18.023111Z'
updated_at: '2026-06-29T14:43:39.454907Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3ceb06a5-aa7f-4d75-bc6d-5f26ee761af3
---
## Summary

Triggered by: OOMPAH-158

### Summary
Add an intake normalization step that rewrites Proposed tasks into the canonical oompah task template before promotion decisions, while preserving user-provided content and making underspecified sections explicit.

### Problem
Intake validation currently determines whether required information is present, but malformed or inconsistent task bodies can remain in the tracker. The TRICKLE-8/OOMPAH-158 case showed that a task can contain the right information while still exposing a null normalized description because the body shape does not match the native task template.

The intake flow should not only validate that information exists; it should also normalize the task body into a predictable structure that agents, humans, the dashboard, and validators can read consistently.

### Desired Behavior
When a user edits a Proposed task or an external GitHub issue is imported, oompah should parse the body, map recognized content into canonical sections, and rewrite the internal task into the proper template. Missing or weak fields should be represented with explicit placeholders such as "Please add more information here", but those placeholders must be machine-marked so validators treat them as missing rather than satisfying readiness.

For external GitHub intake, prefer rewriting the internal native oompah task and commenting on GitHub for missing information rather than rewriting the customer-facing GitHub issue body by default.

### Proposed Workflow
1. User edits an issue or task.
2. Oompah parses and validates the information currently present.
3. Oompah normalizes the internal task body to the canonical template.
4. Missing or underspecified sections are filled with marked placeholders that the validator ignores.
5. If all required information is present, oompah promotes the task from Proposed to Backlog.
6. If information is still missing, oompah leaves the task Proposed and comments with the exact requested additions.

### Acceptance Criteria
- Add a pure parser/normalizer that maps common issue/task body shapes into the canonical native oompah task template.
- Preserve all user-provided content during normalization; do not drop unrecognized sections.
- Insert marked placeholders for missing or underspecified required fields.
- Ensure validators ignore marked placeholder text when determining readiness.
- Run normalization as part of Proposed intake revalidation before Proposed -> Backlog promotion.
- For GitHub issue intake, rewrite the internal native task by default and avoid editing the external GitHub issue body unless a separate explicit configuration enables that.
- Leave tasks in Proposed and post/comment clear missing-field guidance when validation still fails after normalization.
- Add regression tests covering malformed nested-heading bodies like TRICKLE-8, underspecified sections with placeholders, complete issues that promote to Backlog, and GitHub intake behavior that comments externally without rewriting the GitHub issue body.

### Notes
This is a feature follow-up from OOMPAH-158 and the TRICKLE-8 re-evaluation. Keep validation itself pure; the rewrite should be a separate normalization step whose output is then validated.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-29 14:19
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-06-29 14:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-29 14:21
---
Understanding: OOMPAH-159 is NOT a duplicate. OOMPAH-158 (Merged) fixed the H2 heading parsing issue in GitHub intake. OOMPAH-159 is a new feature that adds a normalization step on top: parse any body shape into the canonical oompah task template, insert marked placeholders for missing sections, ensure validators ignore those placeholders, and run this as part of Proposed→Backlog promotion. Searching merged/archived tasks found no existing normalization-related work. Plan: (1) explore intake validator, oompah_md_tracker, and github_intake_bridge to understand current body structure and validation flow; (2) implement a pure normalizer in its own module; (3) hook it into the Proposed intake revalidation pipeline; (4) add regression tests for TRICKLE-8-style bodies, placeholders, GitHub intake behavior; (5) commit and push.
---
author: oompah
created: 2026-06-29 14:33
---
Discovery: Full codebase architecture mapped. Key findings: (1) issue.description = content of ## Summary section in the native task body; validator scans description for H3+ headings; (2) TRICKLE-8 root cause was H2 headings inside ## Summary breaking _section() — fixed in OOMPAH-158 for new imports; old tasks may still be malformed; (3) process_epic_proposal_issue() in epic_proposal.py is the intake processing entry point for Proposed tasks — normalization should run here before validate_issue(); (4) Placeholder format: <!-- oompah:placeholder field='...' --> within section body; validator's _section_nonempty() needs one-line update to recognize it; (5) Normalizer design: pure function normalize_body(body, issue_type) -> (normalized_body, was_changed) that scans ALL headings in body, maps them to canonical fields, builds normalized ## Summary with H3 subsections, adds marked placeholders for missing required fields; (6) Integration: add get_raw_body/set_raw_body to OompahMarkdownTracker; normalize_native_task() integration function; (7) GitHub intake: normalization only touches native tasks, never the external GitHub issue body.
---
author: oompah
created: 2026-06-29 14:42
---
Implementation: Delivered OOMPAH-159. Changes: (1) oompah/intake_normalizer.py — new pure parser/normalizer module; normalize_body(body, issue_type) extracts all headings from the full raw body, maps them to canonical fields (same keyword lists as issue_validator), builds normalized ## Summary with H3 sub-sections, inserts <!-- oompah:placeholder field='...' --> markers for missing required fields, preserves unrecognized sections in ## Notes, keeps ## External GitHub Issue and ## Comments verbatim; normalize_native_task() integration helper is a no-op for non-native trackers so GitHub issue bodies are never rewritten; (2) oompah/issue_validator.py — _section_nonempty() now returns False when section body contains <!-- oompah:placeholder marker; inline_ac_re regex anchored with ^ to prevent HTML comment dashes from falsely matching; (3) oompah/oompah_md_tracker.py — added get_raw_body() and set_raw_body() public methods for full-body access; (4) oompah/epic_proposal.py — process_epic_proposal_issue() now calls normalize_native_task() before validate_issue(), re-fetches the issue if normalized; (5) tests/test_intake_normalizer.py — 46 new tests covering TRICKLE-8 regression, placeholder insertion, idempotency, heading aliases, GitHub intake no-body-rewrite.
---
author: oompah
created: 2026-06-29 14:43
---
Verification: Full test suite run passed. 7192 tests passed, 0 failures, 28 skipped. New tests: 46 in tests/test_intake_normalizer.py covering all acceptance criteria. Key test results: (1) TRICKLE-8 regression — normalize_body() correctly extracts content from malformed nested H2 bodies where _section() returns None; (2) Placeholder insertion — missing required fields get <!-- oompah:placeholder --> markers; (3) Validator ignores placeholders — _section_nonempty() returns False for placeholder content; validate_issue() reports missing fields; (4) GitHub intake no-rewrite — normalize_native_task() is a no-op for trackers without get_raw_body/set_raw_body (all GitHubIssueTracker instances); (5) Idempotency — canonical bodies are unchanged on second normalization. Also fixed a pre-existing bug: inline_ac_re in _validate_common() was matching HTML comment dashes; anchored with ^ to prevent false positives.
---
author: oompah
created: 2026-06-29 14:43
---
Completion: OOMPAH-159 delivered. Implemented: (1) oompah/intake_normalizer.py — pure normalize_body() + normalize_native_task() integration helper; (2) Updated _section_nonempty() in issue_validator.py to treat oompah:placeholder markers as empty; (3) Fixed inline_ac_re false-positive with ^ anchor; (4) Added get_raw_body()/set_raw_body() to OompahMarkdownTracker; (5) Hooked normalize_native_task() into process_epic_proposal_issue() before validate_issue(); (6) 46 regression tests. All acceptance criteria met: pure normalizer, content preserved, marked placeholders, validator ignores them, runs before Proposed->Backlog promotion, GitHub issue bodies not rewritten, 46 tests cover TRICKLE-8/placeholder/promotion/GitHub-intake cases. Branch OOMPAH-159 pushed to origin.
---
author: oompah
created: 2026-06-29 14:43
---
Delivered intake normalization: new oompah/intake_normalizer.py pure module, placeholder-aware _section_nonempty(), get_raw_body/set_raw_body on OompahMarkdownTracker, normalization hooked into process_epic_proposal_issue(), 46 regression tests. All AC met. 7192/7192 tests pass.
---
<!-- COMMENTS:END -->
