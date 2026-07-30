---
id: OOMPAH-594
type: feature
status: Open
priority: 1
title: Reload HTTP Basic credentials safely after htpasswd rotation
parent: OOMPAH-586
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:55.490677Z'
updated_at: '2026-07-30T15:19:59.829585Z'
work_branch: epic-OOMPAH-586--task-OOMPAH-594
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a5877e72c28f883709890b87c9b5e3bd5e5a3cefcb7907fbaf7997fec50b6aa5
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 9bf2369b-6008-413f-bcc4-5cdfeeefe9a6
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T15:19:49.001607+00:00'
  claim_expires_at: '2026-07-30T15:49:49.001607+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 09d41e4d-2221-4cb1-82a4-7b4144af64da
oompah.work_branch: epic-OOMPAH-586--task-OOMPAH-594
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-586--task-OOMPAH-594
  base_branch: epic-OOMPAH-586
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T15:19:57.587599+00:00'
---
## Summary

Implementation scope

Prevent the running service from retaining stale HTTP Basic verifier state after the configured htpasswd file is atomically replaced or updated. Detect safe file identity/content changes, load and validate a complete replacement atomically, preserve the last known-good credentials on parse/read failure, and expose a redacted reload status. Ensure Makefile lifecycle clients and task/admin CLIs use the current .env client inputs; do not pass Basic credentials to workers. Relevant files include oompah/http_auth.py, bootstrap/server auth middleware, client lifecycle helpers, Makefile/scripts/oompah_http.py, and .env.example/operator docs if behavior changes.

Tests

Cover valid rotation, invalid/partial replacement, symlink/path protections, concurrent requests, username removal/addition, unchanged files, restart parity, and secret redaction. Run focused auth/server tests and make test.

Acceptance criteria

Supported credential rotation does not require an unauthenticated force restart; operator status, restart, task, and admin commands authenticate after rotation; malformed updates never disable or weaken auth.

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
created: 2026-07-30 15:19
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 15:19
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
