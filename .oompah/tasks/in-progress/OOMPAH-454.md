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
updated_at: '2026-07-28T13:23:50.096796Z'
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
<!-- COMMENTS:END -->
