---
id: OOMPAH-861
type: task
status: Open
priority: null
title: Keep accepted branch identity immutable after owner-submit gate failure
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T13:27:20.466495Z'
updated_at: '2026-08-06T13:40:59.946648Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-861
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 210ae92181a8873ff8114a0ada021b62c6bd7c15043520e8a66fa5a16d3b94e9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T13:40:56.263764+00:00'
  matched_identifiers: []
  evidence: 'Owner reviewed the authoritative corpus: OOMPAH-815 is the completed
    predecessor whose accepted-branch invariant regressed; OOMPAH-861 records the
    new exact OOMPAH-860 post-accept repair reproduction and is not duplicate active
    work.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-06T13:40:56.263764+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: 'Owner reviewed the authoritative corpus: OOMPAH-815 is
    the completed predecessor whose accepted-branch invariant regressed; OOMPAH-861
    records the new exact OOMPAH-860 post-accept repair reproduction and is not duplicate
    active work.'
oompah.agent_run_id: a33a7b59-e651-4680-887e-dc51f00db7d7
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-861
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-861
  base_branch: epic-OOMPAH-763
  base_sha: 52cf744ab676b50bdb999e9b0feb39bc092418c1
  updated_at: '2026-08-06T13:28:34.258730+00:00'
oompah.task_costs:
  total_input_tokens: 3
  total_output_tokens: 2446
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 3
      output_tokens: 2446
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 3
    output_tokens: 2446
    cost_usd: 0.0
    recorded_at: '2026-08-06T13:30:28.789701+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-861__20260806T132918Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-861
    source_sha: 52cf744ab676b50bdb999e9b0feb39bc092418c1
    completed_at: '2026-08-06T13:30:28.810532+00:00'
---
## Summary

Live OOMPAH-860 regression on 2026-08-06 after OOMPAH-815 reached Done. OOMPAH-860 is a child of OOMPAH-763 with null work_branch. Direct-owner work was prepared on epic-OOMPAH-763--task-OOMPAH-860, but the authenticated submit validator rejected it and required plain OOMPAH-860. The exact same validated head was then pushed/submitted from OOMPAH-860; integration authority recorded task_branch=OOMPAH-860 and the exact full gate ran that branch. When the gate failed, CI repair dispatch recomputed epic-OOMPAH-763--task-OOMPAH-860, found the registered worktree still correctly checked out on the accepted OOMPAH-860 branch, and refused to reset it. This recreates the precise split identity that OOMPAH-815 promised to eliminate. Implementation scope: trace owner-claim submit validation, accepted IntegrationRecord persistence/projection, transition to Needs CI Fix/In Progress, and repair workspace creation; once a branch+head is accepted, persist and reuse that immutable branch for every repair/retry/audit path, including null/stale work_branch and parent status changes. Eliminate any post-accept fallback that recomputes hierarchy; make submit validation and repair resolution use the same canonical resolver/generation. Preserve exact remote-head/ancestry proof, dirty-worktree no-reset safety, concurrent resubmit fencing, and hierarchical branches before acceptance. Required tests: exact OOMPAH-860 sequence (hierarchical submit rejected, plain submit accepted, gate failure, repair reuses plain worktree); restart between acceptance/failure/repair; null and stale work_branch; parent/child status changes after acceptance; concurrent same-head submit; invalid remote/head/ancestry fails before mutation; canonical hierarchical control; no repeated zero-turn dispatch loop. Acceptance: every accepted submission can be repaired on the exact persisted branch without manual checkout/metadata edits, and submit validation can never require a branch that the subsequent repair dispatcher rejects.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 13:28
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-08-06 13:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 13:30
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 2, Tool calls: 0
- Tokens: 3 in / 2.4K out [2.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 1s
- Log: OOMPAH-861__20260806T132918Z.jsonl
---
author: oompah
created: 2026-08-06 13:30
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
<!-- COMMENTS:END -->
