---
id: OOMPAH-463
type: feature
status: Open
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
updated_at: '2026-07-28T18:06:16.406255Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

