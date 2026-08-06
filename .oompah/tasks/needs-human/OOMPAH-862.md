---
id: OOMPAH-862
type: task
status: Needs Human
priority: null
title: Prevent terminal auditors from redundantly rerunning authoritative full gates
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T14:20:47.304513Z'
updated_at: '2026-08-06T14:22:54.975020Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-862
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ea3892ed7b4cfc880dc90345a4c9b957196bea269515ae7e63fb268c0e15c60f
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: 'Required structural peers could not fit the bounded duplicate corpus.
    Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-850, OOMPAH-851, OOMPAH-852,
    OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 3
  retry_after: '2026-08-06T14:22:37.997999+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 31ffd653-fabf-4646-bbab-1de449aec7c9
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-862
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-862
  base_branch: epic-OOMPAH-763
  base_sha: d5edb84f121e08b04d3bd4a7d1e937f3233d5b4c
  updated_at: '2026-08-06T14:21:51.939134+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2503
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2503
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2503
    cost_usd: 0.0
    recorded_at: '2026-08-06T14:22:37.992370+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-862__20260806T142200Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-862
    source_sha: d5edb84f121e08b04d3bd4a7d1e937f3233d5b4c
    completed_at: '2026-08-06T14:22:38.017861+00:00'
---
## Summary

Live OOMPAH-860 regression on 2026-08-06: the exact accepted head completed the configured 16k-test make test gate successfully, and the terminal auditor then launched make test-serial across the entire suite before rendering its independent verdict. This serializes the only validation lane for a long second full run and delays unrelated accepted repairs without adding missing exact-head evidence. Implementation scope: include authoritative exact-head quality-gate command, result, head SHA, duration, and relevant focused evidence in the terminal-audit prompt/evidence bundle; tell auditors to verify the patch and run only narrowly targeted missing checks when the exact configured gate is already current and passing; keep auditors free to request or run a full gate when evidence is missing, stale, failed, mismatched, or the task specifically requires a distinct execution mode. Add observability distinguishing reused authoritative gate evidence, focused supplemental commands, and auditor-initiated full-suite runs. Relevant code: auditor prompt construction and dispatch in oompah/orchestrator.py and oompah/auditor_dispatch.py, quality-gate evidence lookup, terminal audit telemetry, and Completion Auditor focus instructions. Required tests: a current passing exact gate is embedded and suppresses redundant make test or make test-serial guidance; stale/different-head/failed evidence does not suppress a needed gate; focused warning or race checks remain allowed; telemetry records the decision; restart retains the evidence decision. Acceptance criteria: the OOMPAH-860 sequence reaches an independent terminal verdict without a second full-suite run when the exact accepted head already has a passing configured gate, while fail-closed audit behavior remains intact.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 14:21
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 14:21
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 14:22
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.5K out [2.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 54s
- Log: OOMPAH-862__20260806T142200Z.jsonl
---
author: oompah
created: 2026-08-06 14:22
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
<!-- COMMENTS:END -->
