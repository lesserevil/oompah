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
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:08:23.210919Z'
updated_at: '2026-07-29T02:01:48.635704Z'
work_branch: epic-OOMPAH-460
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b97e7d30daa63f7aedc6e2c4faf2a97a83d5897fe6d749753c1ffb151349ccb4
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 39555f81-11cb-4a7d-a0b6-45672a35e35d
  claim_owner: 5d80b10c-0ace-4fc9-8e33-587cf319fe4d
  claimed_at: '2026-07-29T02:01:43.081644+00:00'
  claim_expires_at: '2026-07-29T02:31:43.081644+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 665b280c-1030-420e-a119-379f2cfaff4c
oompah.work_branch: epic-OOMPAH-460
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 02:01
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
