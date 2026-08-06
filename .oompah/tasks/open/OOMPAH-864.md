---
id: OOMPAH-864
type: bug
status: Open
priority: 1
title: Rearm abandoned duplicate-preflight work when an owner returns a task to Open
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T18:12:02.899266Z'
updated_at: '2026-08-06T18:22:59.749899Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-864
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1adcfa5d277fcb50a57de91e98d6e3b03c5c589b5269106064b265e244db4997
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T18:22:55.936438+00:00'
  matched_identifiers: []
  evidence: Project-owner review of the authoritative corpus found no duplicate. OOMPAH-864
    is the distinct owner-resolution rearm bug reproduced by OOMPAH-863/OOMPAH-855;
    its exact transaction, generation fencing, restart recovery, and worktree preservation
    scope is not covered by the cited peers.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-06T18:22:55.936438+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: Project-owner review of the authoritative corpus found
    no duplicate. OOMPAH-864 is the distinct owner-resolution rearm bug reproduced
    by OOMPAH-863/OOMPAH-855; its exact transaction, generation fencing, restart recovery,
    and worktree preservation scope is not covered by the cited peers.
oompah.agent_run_id: f04326f4-28e6-4257-80aa-02f798222dde
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-864
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-864
  base_branch: epic-OOMPAH-763
  base_sha: 54c8abf8fb6c85ca30fc62a9450de600a739eb5d
  updated_at: '2026-08-06T18:14:01.699875+00:00'
oompah.task_costs:
  total_input_tokens: 46277
  total_output_tokens: 287
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46277
      output_tokens: 287
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46277
    output_tokens: 287
    cost_usd: 0.0
    recorded_at: '2026-08-06T18:14:41.833507+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-864__20260806T181414Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-864
    source_sha: 54c8abf8fb6c85ca30fc62a9450de600a739eb5d
    completed_at: '2026-08-06T18:14:41.862888+00:00'
---
## Summary

Live reproduction on OOMPAH-863 (and latent on OOMPAH-855) after an inconclusive duplicate investigator moves an Open task to Needs Human. Duplicate preflight has already created the private worktree and persisted oompah.integration.state=working. The authenticated owner-resolution action records no_duplicate and sets the task to Open, but it neither retires nor rearms that abandoned duplicate-preflight run. Subsequent scheduler ticks report available agent capacity yet normal_dispatch=0 because the stale working record is treated as active; orphan recovery scans In Progress rather than this Open owner-resolved shape. Implementation scope: make successful no_duplicate owner resolution atomically reconcile the exact duplicate-preflight authority/run, work contributor, work branch/worktree, integration record, retry metadata, and tracker status into one dispatchable generation. Reuse a clean matching private worktree safely, preserve dirty/recovery checkpoints and branch identity, fence late output from the retired investigator, and never reset an unrelated implementation/integration owner. Apply the same restart reconciliation when the server stops between verdict persistence and rearm. duplicate_candidate resolutions must remain nondispatchable. Expose a truthful bounded reassessment reason rather than phantom working. Relevant code: _owner_resolve_duplicate_screening and its API transaction, duplicate-preflight completion/retirement, integration working metadata, candidate selection, orphan/liveness reconciliation, and owner-resolution tests. Required tests: exact Open→duplicate preflight→Needs Human→owner no_duplicate lifecycle dispatches implementation on the next bounded tick; crash/restart at each persistence boundary; late investigator completion cannot overwrite the owner verdict/new generation; clean versus dirty worktree; pre-existing unrelated worker authority; duplicate_candidate; repeated idempotent owner resolution; OOMPAH-855 hard-start remains blocked until its real prerequisite. Acceptance criteria: an owner-resolved no_duplicate task has exactly one durable dispatchable or explicitly blocked disposition, never an ownerless working record; OOMPAH-863-style tasks resume without waiting for watchdog age or manual metadata mutation; focused duplicate, ownership, workspace recovery, liveness, and restart tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 18:13
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 18:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 18:14
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.3K in / 287 out [46.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 47s
- Log: OOMPAH-864__20260806T181414Z.jsonl
---
author: oompah
created: 2026-08-06 18:14
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-847, OOMPAH-849, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861, OOMPAH-862, OOMPAH-863. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
<!-- COMMENTS:END -->
