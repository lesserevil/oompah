---
id: OOMPAH-755
type: task
status: Backlog
priority: 1
title: Rebase epic-OOMPAH-740 onto main
parent: OOMPAH-740
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:04:47.253891Z'
updated_at: '2026-08-04T11:04:47.253891Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Task-specific recovery for OOMPAH-741 while OOMPAH-754 fixes automatic stale-ancestry detection. The shared epic branch epic-OOMPAH-740 is 0 commits ahead and 35 commits behind origin/main, so merged prerequisite OOMPAH-735 (head 0c7d9cbd41a03aa8092a0e82e10ec50862e143ed) is not reachable and the integration executor correctly refuses to lease OOMPAH-741. Work directly on epic-OOMPAH-740: fetch origin, rebase the epic branch onto origin/main, resolve only genuine conflicts while preserving all epic work, run the configured focused checks and full Makefile gate as required, and force-push with --force-with-lease. Do not create a separate implementation branch or PR. Verify origin/epic-OOMPAH-740 contains OOMPAH-735 and matches the pushed repaired head; then allow OOMPAH-741 to resume through the existing integration queue. Acceptance criteria: the epic branch contains current main ancestry without losing work; OOMPAH-741 becomes eligible and obtains a lease/attempt on a subsequent queue pass; no queue metadata or private task head is manually rewritten; the helper is submitted through the direct epic-maintenance path.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

