---
id: OOMPAH-792
type: task
status: Open
priority: 1
title: Run all historical systemic incidents as full-stack workflow scenarios
parent: OOMPAH-767
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-789
- OOMPAH-788
- OOMPAH-781
- OOMPAH-782
- OOMPAH-793
- OOMPAH-791
- OOMPAH-804
labels: []
assignee: null
created_at: '2026-08-04T13:59:19.563806Z'
updated_at: '2026-08-06T16:11:03.498433Z'
work_branch: epic-OOMPAH-767--task-OOMPAH-792
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 00c6dc9f9b1664fbf306e3f01847f4abb61a50803db350a17aa072db95634e10
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T16:10:56.309194+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: OOMPAH-792 is related to but not a duplicate of OOMPAH-767. The parent
    epic (OOMPAH-767, In Progress) describes building the entire verification system
    framework (reference model, generators, event injection, multi-project infrastructure,
    100-task soak). OOMPAH-792 (Open) is a focused child task that implements one
    specific component: the scenario test suite for the historical incidents. OOMPAH-792''s
    dependencies on Done tasks (OOMPAH-789, 790, 781, 782, 788, 791, 793, 804) confirm
    it consumes infrastructure prepared elsewhere. The tasks occupy distinct positions
    in the decomposition: OOMPAH-767 builds framework; OOMPAH-792 uses that framework
    to test historical incidents. No other active tasks in the corpus describe this
    same underlying problem.

    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: OOMPAH-792 is related to but not a duplicate of OOMPAH-767. The parent
    epic (OOMPAH-767, In Progress) describes building the entire verification system
    framework (reference model, generators, event injection, multi-project infrastructure,
    100-task soak). OOMPAH-792 (Open) is a focused child task that implements one
    specific component: the scenario test suite for the historical incidents. OOMPAH-792''s
    dependencies on Done tasks (OOMPAH-789, 790, 781, 782, 788, 791, 793, 804) confirm
    it consumes infrastructure prepared elsewhere. The tasks occupy distinct positions
    in the decomposition: OOMPAH-767 builds framework; OOMPAH-792 uses that framework
    to test historical incidents. No other active tasks in the corpus describe this
    same underlying problem.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: cf7204f9-9c9f-4d0a-8f37-982239ab4967
oompah.work_branch: epic-OOMPAH-767--task-OOMPAH-792
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-767--task-OOMPAH-792
  base_branch: epic-OOMPAH-767
  base_sha: 6ae941a31682dce6cd9346c3c4d7116a4c2db8ae
  updated_at: '2026-08-06T16:09:38.499631+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 4652
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 4652
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 4652
    cost_usd: 0.0
    recorded_at: '2026-08-06T16:10:56.307753+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-792__20260806T161000Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-767--task-OOMPAH-792
    source_sha: 6ae941a31682dce6cd9346c3c4d7116a4c2db8ae
    completed_at: '2026-08-06T16:10:56.328308+00:00'
---
## Summary

Use the shared incident corpus to build full-stack scenarios spanning fact collectors, evaluator, job ledger/worker, transition service, native tracker, Git, and UI projection for OOMPAH-562/731/732/739/748/749/751. Avoid mocking the exact boundary whose composition caused the incident. Verify both safety and bounded natural recovery, including server restart and event duplication. Acceptance: every historical workaround scenario progresses without manual status/queue/branch mutation and produces the same reason in executor and UI.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 16:08
---
All seven hard-start prerequisites are terminal and the live dependency audit found no remaining start blocker. Promoted to Open so the managed server can implement the historical full-stack scenario suite in parallel with operator-owned repair integration.
---
author: oompah
created: 2026-08-06 16:09
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 16:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 16:10
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 4, Tool calls: 0
- Tokens: 10 in / 4.7K out [4.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 25s
- Log: OOMPAH-792__20260806T161000Z.jsonl
---
<!-- COMMENTS:END -->
