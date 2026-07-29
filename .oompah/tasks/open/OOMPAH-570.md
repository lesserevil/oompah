---
id: OOMPAH-570
type: bug
status: Open
priority: 1
title: Recover interrupted integration leases and explicit blocked-head retries
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T23:53:31.874608Z'
updated_at: '2026-07-29T23:55:55.010049Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 70211f087949bc92d36b39a24ee18fe20444239fd436a12269a096e08f38a265
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: Duplicate-screening worker exited with reason normal.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: '2026-07-29T23:56:49.587719+00:00'
oompah.agent_run_id: c5e8cfe2-bd7d-48c1-8c97-1cd456726881
oompah.task_costs:
  total_input_tokens: 162
  total_output_tokens: 6639
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 162
      output_tokens: 6639
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 162
    output_tokens: 6639
    cost_usd: 0.0
    recorded_at: '2026-07-29T23:55:49.586880+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-570__20260729T235353Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-570
    source_sha: 8483db2e3e718c1f5f6476018d954574ce5d42f9
    completed_at: '2026-07-29T23:55:49.595678+00:00'
---
## Summary

Triggered by: OOMPAH-562

Implementation scope: make durable epic-child integration recover promptly after a service exec/restart interrupts an in-flight quality gate, and make an explicit task submission able to retry a blocked queue row even when task_branch and head_sha are unchanged. Preserve idempotency for periodic Ready-to-Integrate synchronization and for ready/integrating/integrated rows so no automatic retry loop or duplicate integration is introduced. Add an explicit retry flag or equivalent boundary between the submit API path and background queue synchronization. On orchestrator startup, safely identify/requeue abandoned integrating leases; ensure any active branch-quality-gate process group is terminated during shutdown before leases become reclaimable. Relevant files: oompah/integration_queue.py, oompah/orchestrator.py, oompah/quality_gate.py, server submission wiring, and their tests. Tests: reproduce (1) blocked identical explicit resubmit versus background sync, (2) restart with a durable integrating row and rebased private head, (3) shutdown process-tree cleanup, and (4) no duplicate claims/integration. Acceptance criteria: an operator never waits for the hour-long lease after a normal restart, a same-head explicit resubmit clears a blocked row without branch-name workarounds, background sync remains idempotent, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 23:53
---
Accepted for implementation after live queue recovery exposed the restart-lease and same-head retry gaps.
---
author: oompah
created: 2026-07-29 23:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 23:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 23:55
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 67, Tool calls: 40
- Tokens: 162 in / 6.6K out [6.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 58s
- Log: OOMPAH-570__20260729T235353Z.jsonl
---
<!-- COMMENTS:END -->
