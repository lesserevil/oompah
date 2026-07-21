---
id: OOMPAH-287
type: task
status: Backlog
priority: 1
title: Add provenance metadata for external content entering Oompah
parent: OOMPAH-285
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T14:51:40.852361Z'
updated_at: '2026-07-21T14:51:40.852361Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement the provenance model from the threat-model task. Extend normalized issue, comment, and attachment representations so content records identify source, trust level, origin URL/actor where available, and whether content may be rendered to a model. Cover GitHub issue bodies/comments, PR metadata, webhook strings, CI/log excerpts, repository text, and attachments. Preserve backward compatibility for native tasks.

Dependency: Define the external-content trust model and prompt-injection threat model.

Tests: unit tests for every source, legacy native-task compatibility, serialization, and default-deny behavior for unknown sources.

Acceptance criteria: prompt code distinguishes trusted operator/task instructions from untrusted external text without parsing prose or source-specific fields.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

