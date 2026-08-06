---
id: OOMPAH-855
type: task
status: Open
priority: null
title: Preserve auditor candidate eligibility across operator pause retirement
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-854
labels: []
assignee: null
created_at: '2026-08-06T06:52:17.206143Z'
updated_at: '2026-08-06T18:00:34.955614Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-855
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0ad2f9dc5c677ad6cd902f1e9c2c86707b47b775130aff56c10ad27c67567388
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T18:00:31.418473+00:00'
  matched_identifiers: []
  evidence: Project-owner review of the complete active systemic-workflow corpus found
    no equivalent task. OOMPAH-855 uniquely preserves auditor candidate eligibility
    across scheduler pause/graceful quiesce retirement. The corpus-capacity inconclusive
    path is the already-fixed OOMPAH-853 deployment gap, not evidence of a duplicate.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-06T18:00:31.418473+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: Project-owner review of the complete active systemic-workflow
    corpus found no equivalent task. OOMPAH-855 uniquely preserves auditor candidate
    eligibility across scheduler pause/graceful quiesce retirement. The corpus-capacity
    inconclusive path is the already-fixed OOMPAH-853 deployment gap, not evidence
    of a duplicate.
oompah.agent_run_id: 96b97b3c-86ea-4de3-b681-871074de63c9
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-855
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-855
  base_branch: epic-OOMPAH-763
  base_sha: 6b67846406858b585ce47939f70bec76eb706fe8
  updated_at: '2026-08-06T16:31:12.980404+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2744
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2744
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2744
    cost_usd: 0.0
    recorded_at: '2026-08-06T16:32:35.675392+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-855__20260806T163128Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-855
    source_sha: 6b67846406858b585ce47939f70bec76eb706fe8
    completed_at: '2026-08-06T16:32:35.707636+00:00'
---
## Summary

Live regression on OOMPAH-853 on 2026-08-06. A Done auditor using the second eligible candidate was retired by the global operator pause used to fence a duplicate implementation writer. The retirement was recorded as a consumed attempt. After resume, both configured candidates were considered attempted and the exact unchanged audit moved to Needs Human for no independent candidate. An owner override was required even though the exact-head gate had passed and the interrupted auditor reported no code defect. Implementation scope: classify scheduler pause and graceful quiesce retirement separately from provider, policy, verdict, transport, timeout, and operator-cancel failures; preserve or immediately requeue the same candidate eligibility when no structured verdict was committed; fence late output from the retired runtime; keep genuine policy denials and repeated provider failures consuming or rotating attempts as configured; make recovery idempotent across pause, resume, and restart. Relevant code includes orchestrator pause and worker retirement, auditor dispatch attempt persistence, terminal audit workflow recovery, and exhaustion classification. Required tests: barrier-pause an auditor before verdict, resume, and prove one retry without Needs Human or attempt-budget consumption; repeat across restart; cover pause after durable verdict finalization without duplicate apply; cover mixed first-candidate policy denial plus second-candidate pause; prove explicit owner cancellation and genuine policy or transport failure retain current semantics. Acceptance criteria: routine pause or graceful drain cannot turn an otherwise healthy unchanged audit into no-independent-candidate exhaustion; exact evidence and candidate independence remain fail-closed; focused pause, auditor lifecycle, durable workflow, and terminal-transition tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 16:30
---
Promoted for the systemic completion program with an explicit hard-start on OOMPAH-854. The pause-retirement eligibility repair depends on OOMPAH-854 durable pre-provider audit fencing and must dispatch from that accepted lineage, avoiding a second overlapping quiesce/restart implementation.
---
author: oompah
created: 2026-08-06 16:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 16:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 16:32
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.7K out [2.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 32s
- Log: OOMPAH-855__20260806T163128Z.jsonl
---
author: oompah
created: 2026-08-06 16:33
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861, OOMPAH-862. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
<!-- COMMENTS:END -->
