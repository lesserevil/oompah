---
id: OOMPAH-592
type: feature
status: Open
priority: 1
title: Alert on terminal-audit launch failures and backlog age
parent: OOMPAH-585
children: []
blocked_by:
- OOMPAH-589
- OOMPAH-590
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:28.755226Z'
updated_at: '2026-07-30T14:33:49.780782Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-592
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e63ac8087f03fa3d8e428789060b5e66d27092edde9c2b197433ace96b4cd4ac
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 81391cf6-6098-4a2e-b53c-c1acb7e7ca09
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T14:33:42.372992+00:00'
  claim_expires_at: '2026-07-30T15:03:42.372992+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 1cce0104-b4ac-4d43-b8dd-210408ca687a
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-592
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-592
  base_branch: epic-OOMPAH-585
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T14:33:47.773679+00:00'
---
## Summary

Implementation scope

Extend terminal-audit health so the operator alert surface includes auditor launch/transport failure counts, oldest pending age, retry exhaustion, and stale In Validation records. Keep the existing enforcement/quarantine signal distinct but aggregate them into truthful project/service health. Alerts must clear only after underlying recovery and must not expose provider secrets or model output. Relevant files include terminal audit health/metrics, oompah/server.py state and alerts APIs, and dashboard rendering.

Tests

Cover empty backlog, fresh normal queue, aged backlog, repeated launch failures, exhausted candidates, successful recovery/clear, restart persistence, and redaction. Run focused API/dashboard tests and make test.

Acceptance criteria

A state with failed auditor launches or materially stale pending audits cannot show an empty healthy alert list; recovered normal operation clears the alert deterministically.

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
created: 2026-07-30 14:33
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 14:33
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
