---
id: OOMPAH-620
type: feature
status: Open
priority: 1
title: Resolve CLI Basic-auth credentials from argv, environment, and netrc
parent: OOMPAH-619
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:25:27.860280Z'
updated_at: '2026-07-30T21:34:13.605614Z'
work_branch: epic-OOMPAH-619--task-OOMPAH-620
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a69aafc49ff23ba2ca61f7c2d748dc05e6565b663fa6eb377db2671593bd3000
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 9740cc62-2f4c-4570-b02a-e6857b608726
  claim_owner: c1f4a4cb-217d-4c2a-aad6-f768a3cdbb4b
  claimed_at: '2026-07-30T21:34:03.475497+00:00'
  claim_expires_at: '2026-07-30T22:04:03.475497+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 18d55605-07c5-472c-9162-c02d736a9f1e
oompah.work_branch: epic-OOMPAH-619--task-OOMPAH-620
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-619--task-OOMPAH-620
  base_branch: epic-OOMPAH-619
  base_sha: c048ba706cbe9b1342b80a67576a49b82887e84a
  updated_at: '2026-07-30T21:34:09.960869+00:00'
---
## Summary

Implementation scope: extend the shared client credential resolver and every standalone HTTP CLI parser so task and admin commands accept explicit --username and --password as well as the existing --password-file. Continue supporting OOMPAH_SERVER_USERNAME with OOMPAH_SERVER_PASSWORD or OOMPAH_SERVER_PASSWORD_FILE. When no higher-precedence value supplies a complete usable credential, read the entry for the normalized hostname of the resolved OOMPAH server URL from the default user netrc file. Username precedence is CLI, environment, then netrc; password precedence is one CLI password source, one environment password source, then the matching netrc password. Reject conflicting same-tier password sources, partial credentials, a netrc password paired with a different overridden login, malformed or unsafe default netrc data, and credentials embedded in URLs. Do not retry a 401 with a lower-precedence source. Keep secrets out of repr, errors, logs, telemetry, and request URLs. Explicit --password is an opt-in compatibility path whose help warns that argv can be visible in process listings; retain password-file as the safer explicit option. Relevant files include oompah/client_auth.py, oompah/task_cli.py, oompah/admin_cli.py, and their existing auth tests. Tests must cover each source independently, mixed field precedence compatible with existing behavior, conflicts, hostname and port normalization, missing and malformed netrc, permission behavior, IPv4 and IPv6 server URLs where supported, redaction, unauthenticated servers, and real task/admin requests through a local test server. Acceptance criteria: both task and admin CLI surfaces authenticate successfully with all three requested source families; precedence is deterministic and documented in help; no secret appears in observable errors or test logs; focused auth/CLI suites and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:34
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 21:34
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
