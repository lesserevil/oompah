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
updated_at: '2026-08-06T07:19:19.395961Z'
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
  evidence: Task state or duplicate-relevant content changed while screening was running.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: '2026-08-06T07:19:13.200426+00:00'
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
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1663
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1663
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1663
    cost_usd: 0.0
    recorded_at: '2026-08-06T07:19:13.198992+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-857__20260806T071848Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-740--task-OOMPAH-857
    source_sha: 4cdcc7e6e4f2f13087bce5942edf6a19821b9979
    completed_at: '2026-08-06T07:19:13.218274+00:00'
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
author: oompah
created: 2026-08-06 07:19
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 50s
- Log: OOMPAH-857__20260806T071848Z.jsonl
---
<!-- COMMENTS:END -->
