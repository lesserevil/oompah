---
id: OOMPAH-806
type: bug
status: Open
priority: 1
title: Fence stalled-task recovery behind internal gate authority
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T20:44:00.064452Z'
updated_at: '2026-08-04T20:47:20.540756Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-806
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 37a03c9984f7a48928f4dc44a6e6eac2a049d5deec92e4d74a806a7e80609853
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T20:47:13.660470+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Closest active tasks are OOMPAH-803, OOMPAH-768, OOMPAH-769,\
    \ and OOMPAH-770. They cover transition-service routing, integration-domain migration,\
    \ generation fencing, and liveness generally, but none specifically addresses\
    \ external CI overriding an authoritative failed exact-head internal gate and\
    \ cancelling its blocked integration generation. OOMPAH-806 is a distinct incident\
    \ regression requiring explicit precedence and race/restart tests.\nFocus handoff:\
    \ duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \nMatches:\
    \ none\n\nEvidence: Closest active tasks are OOMPAH-803, OOMPAH-768, OOMPAH-769,\
    \ and OOMPAH-770. They cover transition-service routing, integration-domain migration,\
    \ generation fencing, and liveness generally, but none specifically addresses\
    \ external CI overriding an authoritative failed exact-head internal gate and\
    \ cancelling its blocked integration generation. OOMPAH-806 is a distinct incident\
    \ regression requiring explicit precedence and race/restart tests."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: c06e16d0-6d62-4572-861d-aff8474a00b0
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-806
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-806
  base_branch: epic-OOMPAH-763
  base_sha: f1e7925b7263f980517f943291102c8c83335ed2
  updated_at: '2026-08-04T20:45:03.904895+00:00'
oompah.task_costs:
  total_input_tokens: 47917
  total_output_tokens: 291
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 47917
      output_tokens: 291
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 47917
    output_tokens: 291
    cost_usd: 0.0
    recorded_at: '2026-08-04T20:47:13.658330+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-806__20260804T204517Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-806
    source_sha: f1e7925b7263f980517f943291102c8c83335ed2
    completed_at: '2026-08-04T20:47:13.706379+00:00'
---
## Summary

Live reproduction on 2026-08-04: OOMPAH-793's exact-head combined-tree integration gate failed at ef5e8c30e (integration row blocked; task Needs CI Fix). Minutes later the stalled-task watchdog observed unrelated passing external commit CI, reopened the task to Open, and the integration reconciler cancelled the blocked row because tracker state was Open. This discarded the authoritative internal gate failure and could expose completed implementation to duplicate dispatch; only an existing direct-owner lease prevented churn. Implementation scope: make current internal integration/gate records and exact-head authority outrank generic forge CI when classifying Needs CI Fix/Ready to Integrate; never reopen or cancel a blocked integration generation based solely on external CI for the same or another check suite; require a newer pushed head, explicit same-generation integration retry, or authoritative repair evidence; serialize watchdog and integration transitions through TaskTransitionService with generation CAS; keep actionable blocked evidence visible to UI/liveness. Relevant code: oompah/stalled_task_watchdog.py, orchestrator watchdog evidence/action plumbing, integration queue reconciliation/executor, TaskTransitionService, and state/alert projections. Required deterministic tests: reproduce blocked combined-tree gate plus passing external CI; watchdog performs no Open transition and row remains blocked; newer repaired head may reopen/resubmit exactly once; race watchdog vs gate completion has one generation winner; restart preserves precedence; unrelated project/task CI cannot influence it; direct-owner absence still cannot cause duplicate implementation dispatch. Acceptance: an internal failed gate remains authoritative until repaired or explicitly retried, watchdog recovery cannot cancel or regress its integration generation, and OOMPAH-793-style churn cannot recur.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 20:44
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-04 20:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 20:47
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 47.9K in / 291 out [48.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 19s
- Log: OOMPAH-806__20260804T204517Z.jsonl
---
<!-- COMMENTS:END -->
