---
id: OOMPAH-595
type: feature
status: Open
priority: 1
title: Expose separate operator and worker task-auth health signals
parent: OOMPAH-586
children: []
blocked_by:
- OOMPAH-593
- OOMPAH-594
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:56.897824Z'
updated_at: '2026-07-30T15:28:55.195288Z'
work_branch: epic-OOMPAH-586--task-OOMPAH-595
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5599144d8549cf413f0b3bfec2f0109e3cca03737c85cfab4397a53213de6eb8
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 5dc3b8d9-4489-4749-921d-64ec1b99aa85
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T15:28:44.156628+00:00'
  claim_expires_at: '2026-07-30T15:58:44.156628+00:00'
  retry_count: 1
  retry_after: null
oompah.agent_run_id: 9f602516-7a40-4407-87b7-09f436ce9be1
oompah.work_branch: epic-OOMPAH-586--task-OOMPAH-595
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-586--task-OOMPAH-595
  base_branch: epic-OOMPAH-586
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T15:28:53.241502+00:00'
---
## Summary

Implementation scope

Add safe health probes and alerts that distinguish operator Basic-auth configuration drift from scoped task-handoff capability failures. Count/redact 401 and 403 outcomes by authentication path, report whether a worker token was minted and accepted without reporting the token, and provide actionable operator guidance. Avoid alerting on intentional unrelated-task denial. Relevant files include task_handoff instrumentation, task CLI/server middleware, service health/alerts APIs, dashboard, and docs troubleshooting.

Tests

Cover healthy operator and worker paths, stale operator credentials, missing/expired worker token, intentional scope denial, alert clear after recovery, restart persistence where appropriate, and redaction. Run focused auth/health/UI tests and make test.

Acceptance criteria

Operators can tell which authentication plane failed and how to recover it; secrets/capabilities never appear in logs, state JSON, alerts, or task comments.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 15:22
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 15:27
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 23
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 4m 20s
- Log: OOMPAH-595__20260730T152251Z.jsonl
---
author: oompah
created: 2026-07-30 15:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:28
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
