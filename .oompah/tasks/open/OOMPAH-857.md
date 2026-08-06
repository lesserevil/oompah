---
id: OOMPAH-857
type: task
status: Open
priority: null
title: Clear recovered operator-auth warnings after authenticated success
parent: OOMPAH-740
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T07:17:16.417571Z'
updated_at: '2026-08-06T07:18:33.844254Z'
work_branch: epic-OOMPAH-740--task-OOMPAH-857
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: fc362989f4a280b1657e990a6bc0fabb3e60f4fd95a6eb3d75b9753e465a78f2
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 2c5cd98e-6667-4b32-b451-0cf2864c257e
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-06T07:18:18.910290+00:00'
  claim_expires_at: '2026-08-06T07:48:18.910290+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 7257a8b4-a4ae-4643-bc30-d7c87ff846a5
oompah.work_branch: epic-OOMPAH-740--task-OOMPAH-857
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-740--task-OOMPAH-857
  base_branch: epic-OOMPAH-740
  base_sha: 4cdcc7e6e4f2f13087bce5942edf6a19821b9979
  updated_at: '2026-08-06T07:18:28.943121+00:00'
---
## Summary

A failed operator Basic-auth probe currently leaves auth_health:operator styled as an actionable warning for the full rolling window even after the same configured principal successfully authenticates. The message then prescribes regenerating htpasswd and restarting a healthy server, which is false and displaces the dashboard despite current proof that credentials work.

Implementation scope:
- Separate rolling authentication failure telemetry from current credential-health actionability.
- Record successful authenticated operator probes with principal/config generation context and reclassify or clear stale credential-mismatch warnings when current credentials demonstrably succeed.
- Preserve security visibility for unexplained failures from other principals/sources and for continuing failures with no subsequent success; never expose credentials or weaken authentication.
- Ensure the dashboard receives the authoritative removal/reclassification through the existing sequenced state stream without refresh.

Relevant code: operator Basic-auth middleware/counters and auth-health serialization in oompah/server.py and related auth-health modules, dashboard alert normalization/rendering in oompah/templates/dashboard.html, and auth/alert tests under tests/.

Required tests:
- Failed configured-principal request followed by successful authenticated request clears or demotes the credential-mismatch action without waiting 15 minutes.
- Continuing failures remain actionable with correct remediation.
- Failures attributable to a different/unknown principal remain security telemetry without being falsely declared recovered.
- A sequenced authoritative state update removes the stale warning in the browser model.

Acceptance criteria:
- A healthy authenticated operator session never displays instructions to regenerate working credentials or restart solely because of an earlier recovered probe.
- Historical failure counts remain available as bounded diagnostics, while only current operator actionability occupies the warning surface.
- Focused auth-health, state-stream, and dashboard alert tests plus make test pass.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 07:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 07:18
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
