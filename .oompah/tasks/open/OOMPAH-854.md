---
id: OOMPAH-854
type: task
status: Open
priority: null
title: Fence terminal-auditor admission during quiesce and restart drain
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T05:46:04.066694Z'
updated_at: '2026-08-06T06:18:59.172232Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-854
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b55033ee11bfb470f03a931536f978a7e592379c31932410e3bbc9123a91e375
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T06:18:55.826933+00:00'
  matched_identifiers: []
  evidence: Project-owner review of authoritative structural peers OOMPAH-847, OOMPAH-848,
    OOMPAH-850, OOMPAH-851, OOMPAH-852, and OOMPAH-853 found related validation-lane
    work but no task duplicating the terminal-auditor admission race during quiesce.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-06T06:18:55.826933+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: Project-owner review of authoritative structural peers
    OOMPAH-847, OOMPAH-848, OOMPAH-850, OOMPAH-851, OOMPAH-852, and OOMPAH-853 found
    related validation-lane work but no task duplicating the terminal-auditor admission
    race during quiesce.
oompah.agent_run_id: 01428d09-dbb0-4958-bc63-f1183ad4b011
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-854
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-854
  base_branch: epic-OOMPAH-763
  base_sha: 930cd74b9ccbffcae5579c960f4298a8b86b26c7
  updated_at: '2026-08-06T06:10:09.285412+00:00'
oompah.task_costs:
  total_input_tokens: 46364
  total_output_tokens: 347
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46364
      output_tokens: 347
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46364
    output_tokens: 347
    cost_usd: 0.0
    recorded_at: '2026-08-06T06:10:36.799497+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-854__20260806T061024Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-854
    source_sha: 930cd74b9ccbffcae5579c960f4298a8b86b26c7
    completed_at: '2026-08-06T06:10:36.816817+00:00'
---
## Summary

Live reproduction at 2026-08-06T05:43Z: make restart had quiesced build fe6257b and drained the only running OOMPAH-821 auditor to an accepted Done verdict. Instead of reaching running=0, the terminal-audit scheduler launched two new provider processes for queued OOMPAH-791 and OOMPAH-852 audits while /api/v1/state still reported quiesced=true, increasing counts.running from 0 to 2 and extending the graceful cutover indefinitely. Implementation scope: apply the same dispatch-admission fence used for implementation workers to terminal-audit dequeue/claim/provider launch; atomically re-check quiesced/paused/restart state immediately before durable running transition and provider spawn; preserve queued audit records without incrementing attempts; allow already-running auditors to drain; resume queued audits exactly once after the new instance is healthy; fence quiesce versus audit completion/requeue races and direct restart with a generation/CAS so no late callback can launch after an empty drain observation. Relevant code: orchestrator terminal-audit enforcement/dequeue paths, auditor dispatch/provider launch, quiesce/restart lifecycle, running-count snapshot, and terminal audit persistence recovery. Required tests: queue two audits, quiesce as the current auditor exits, prove running reaches/stays zero and no provider/worktree launch occurs; restart and prove both preserved audits dispatch exactly once; cover audit retry/requeue racing quiesce, paused startup, failed provider launch, direct force-independent lifecycle recovery, and dashboard counts. Acceptance criteria: once quiesced, no new auditor can enter running or create a provider process; graceful restart time is bounded only by work already running at quiesce; queued audits survive and resume naturally on the healthy new instance; focused lifecycle/auditor tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 06:10
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 06:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 06:10
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.4K in / 347 out [46.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 38s
- Log: OOMPAH-854__20260806T061024Z.jsonl
---
author: oompah
created: 2026-08-06 06:10
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
<!-- COMMENTS:END -->
