---
id: OOMPAH-484
type: feature
status: Open
priority: 1
title: Expose safe terminal-audit state in project, task, and activity APIs
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-483
labels: []
assignee: null
created_at: '2026-07-28T13:08:23.210919Z'
updated_at: '2026-07-28T18:07:03.182740Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Add a safe audit summary to task list/detail responses, project status, running/retrying agent snapshots, and the activity endpoint. Include requested terminal target, queue/running/result phase, attempt count, evidence fingerprint prefix and source/target SHAs, safe contributor/auditor provider-model identities, latest verdict/classification/summary, timestamps, and owner override flag. Never expose credentials, prompts, full diffs, hidden tracker metadata, or untrusted model output. Keep legacy fields unchanged and omit/null the summary for grandfathered or never-audited tasks.

Tests

Add API serialization/redaction tests for queued, running, passed, failed, overridden, grandfathered, malformed metadata, and ACP unknown model records. Verify list/detail/activity agree and existing API consumers remain compatible. Run focused tests and make test.

Acceptance criteria

UI and operators can understand audit state from stable safe APIs without parsing comments or tracker metadata, and no sensitive content is exposed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

