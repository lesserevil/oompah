---
id: OOMPAH-285
type: epic
status: Merged
priority: 1
title: Defend Oompah agents against prompt injection from external content
parent: null
children:
- OOMPAH-286
- OOMPAH-287
- OOMPAH-288
- OOMPAH-289
- OOMPAH-290
- OOMPAH-291
- OOMPAH-335
blocked_by: []
labels:
- epic:rebasing
assignee: null
created_at: '2026-07-21T14:51:29.425206Z'
updated_at: '2026-07-22T00:03:36.107886Z'
work_branch: epic-OOMPAH-285
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/487
review_number: '487'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/487
oompah.review_number: '487'
oompah.work_branch: epic-OOMPAH-285
oompah.target_branch: main
---
## Summary

Goal

Establish defense-in-depth prompt-injection protections for all untrusted externally sourced text that can influence Oompah agents or models, especially GitHub issue bodies/comments, PR metadata, webhook fields, CI/log excerpts, repository documentation, and attachments.

Security requirements

- Treat external text as data, never as trusted instructions.
- Preserve useful issue content while carrying provenance and trust metadata end-to-end.
- Delimit untrusted material in model prompts and prohibit following instructions inside it.
- Keep authority for state transitions, tool access, secrets, Git writes, network actions, and release actions in server-side policy.
- Add regression and adversarial tests; do not rely on keyword blocking alone.

Delivery

Implement children in dependency order. Update the threat model and operator documentation. All code changes require tests; the final integration task runs make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 00:02
---
YOLO: merged PR #487.
---
<!-- COMMENTS:END -->
