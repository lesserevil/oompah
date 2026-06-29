---
id: OOMPAH-159
type: feature
status: In Progress
priority: null
title: Normalize Proposed task bodies during intake validation
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-29T14:14:18.023111Z'
updated_at: '2026-06-29T14:19:41.394131Z'
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
<!-- COMMENTS:END -->
