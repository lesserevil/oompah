---
id: OOMPAH-454
type: bug
status: In Progress
priority: 1
title: Recover GitLab webhook event parity onto main
parent: OOMPAH-451
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T12:34:52.642232Z'
updated_at: '2026-07-28T13:25:34.163007Z'
work_branch: epic-OOMPAH-451
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 6dc953d0-8070-41a0-9586-f9d505de83f0
oompah.work_branch: epic-OOMPAH-451
---
## Summary

Problem: OOMPAH-340 is marked Merged, but current main parse_gitlab_webhook handles only Merge Request Hook. The completed Push, Issue, Note, Pipeline, and Job parsing and server processing remain only in commit 2b3312672 on origin/epic-OOMPAH-318.

Implementation scope: reconcile the event normalization and server handling onto current oompah/webhooks.py and oompah/server.py. Preserve forge-aware project matching, per-project secret validation, delivery deduplication, task/review cache invalidation, and tracked-branch refresh behavior.

Tests: restore/update the stranded TestParseGitLabWebhook and GitLab endpoint cases for push, issue, note, pipeline, job, merge request, malformed payload, wrong forge, duplicate delivery, and secret rejection; run make test.

Acceptance criteria: every documented GitLab event type is authenticated, normalized, and routed through the EventBus on main; push events refresh tracked branches; invalid or duplicate deliveries cause no downstream mutation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 13:23
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 13:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 13:24
---
Understanding: duplicate-detector pass will compare OOMPAH-454 against prior GitLab webhook tasks (especially OOMPAH-340 and related epic work), including full descriptions/comments and current branch history. I will not modify code in this focus; a confirmed duplicate will be archived, otherwise I will document evidence and hand off for implementation.
---
author: oompah
created: 2026-07-28 13:25
---
Discovery: confirmed duplicate of OOMPAH-452's completed recovery work. OOMPAH-452 explicitly cherry-picked stranded OOMPAH-340 commit 2b3312672 onto epic-OOMPAH-451 as 4c215500f, along with OOMPAH-341/342 lifecycle, authentication, and dedup support, then opened PR #558 to main. The two OOMPAH-340 commits have identical stable patch ID 00ff809121d96ecedfc0cd083b35ffc82994b5fc. Current branch contains Push/Issue/Note/Pipeline/Job/Merge Request parsing, server routing and cache/refresh handling, GitLabEventDedup, and the restored parser/endpoint tests. OOMPAH-340 alone was not a sufficient duplicate because its code was stranded; OOMPAH-452 is the recovery task that actually covers this issue.
---
author: oompah
created: 2026-07-28 13:25
---
Implementation: none by design; duplicate-detector rules prohibit a second implementation. OOMPAH-454's requested changes and tests are already present on this branch through OOMPAH-452 / PR #558.
---
author: oompah
created: 2026-07-28 13:25
---
Verification: read-only duplicate verification passed. Stable patch IDs for stranded 2b3312672 and recovered 4c215500f are identical; git log main..HEAD includes recovered OOMPAH-340/341/342 commits; source and tests enumerate all required GitLab hook types, deduplication, and tracked-branch refresh behavior. No new tests were run because this focus made no code changes; OOMPAH-452 recorded 12,324 passed, 39 skipped after recovery.
---
<!-- COMMENTS:END -->
