---
id: OOMPAH-324
type: task
status: In Progress
priority: 2
title: Generalize external issue intake and provenance for GitLab
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-323
labels: []
assignee: null
created_at: '2026-07-21T20:34:26.149163Z'
updated_at: '2026-07-22T05:46:07.780160Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 52472b1d-5fb9-4471-8e43-3af73b3cb8ad
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, GitLab implementation.

Refactor github_intake_bridge into a forge-neutral external-intake service while keeping compatibility wrappers for existing callers. Add GitLab native-task intake: import issues and comments once, store provider-specific external metadata under oompah.external.gitlab, synchronize terminal task comments/closure back to GitLab, and route GitLab webhook events to the bridge. Extend prompt provenance enums, wrappers, and threat-model documentation so GitLab issue/MR/comment/webhook/CI text is untrusted.

Tests:
- GitHub regression suite remains green through compatibility paths.
- GitLab issue create/update/comment/close/reopen import and idempotency fixtures.
- Terminal mirror behavior and metadata lookup.
- Prompt delimiter/provenance tests proving GitLab content cannot become trusted instructions.

Acceptance criteria:
- Native Markdown projects may enable GitLab issue intake with the same behavior as GitHub intake.
- External IDs and metadata never collide across providers.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:46
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:46
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
