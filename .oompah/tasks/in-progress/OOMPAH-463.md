---
id: OOMPAH-463
type: feature
status: In Progress
priority: 1
title: Persist terminal-audit state through the tracker metadata contract
parent: OOMPAH-457
children: []
blocked_by:
- OOMPAH-462
- OOMPAH-452
labels: []
assignee: null
created_at: '2026-07-28T13:05:05.235115Z'
updated_at: '2026-07-28T18:39:59.541752Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: c1135c8e-b69c-4657-84b0-9e2baac7fbb2
oompah.work_branch: epic-OOMPAH-457
---
## Summary

Implementation scope

Add tracker-neutral helpers that read and write a single namespaced oompah.terminal_audit metadata document containing the pending chain and bounded audit-attempt history. Use TrackerProtocol.get_metadata/set_metadata_field and the per-project write lock; do not parse human comments as authority. Implement no-op detection so polling does not create metadata-only commits when the document is unchanged. Cover native Markdown, GitHub body metadata, and GitLab metadata once the GitLab adapter is available. Preserve unknown future fields during updates.

Tests

Add contract tests for empty metadata, round trips, append/update, no-op writes, unknown-field preservation, concurrent serialized updates, malformed-document quarantine, and secret redaction for each tracker adapter. Run focused tests and make test.

Acceptance criteria

Audit state survives process restart and tracker rereads, concurrent writers cannot silently drop attempts, unchanged writes are true no-ops, and no secret or full model response reaches tracker metadata.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:39
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:39
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
