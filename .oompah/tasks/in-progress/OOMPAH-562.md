---
id: OOMPAH-562
type: bug
status: In Progress
priority: 1
title: Recover integration queues blocked by stale epic ancestry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T21:08:21.827812Z'
updated_at: '2026-07-29T21:18:39.662918Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9cdd0dccc0633a668b1bb9eda0106229ecc2b0c8e3e4dd82f57bfa96388450cc
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T21:17:53.197353+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Active OOMPAH-281 and OOMPAH-282 are unrelated. Closest\
    \ reviewed terminal tasks\u2014OOMPAH-165, OOMPAH-168, OOMPAH-177, OOMPAH-253,\
    \ and OOMPAH-264\u2014cover adjacent epic detection, orchestration, queueing,\
    \ or rebase behavior but not stale-ancestry recovery for integration queues. No\
    \ files or tracker state were modified."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 00021a4c-ff96-47d6-b846-ffece2d2f18a
oompah.task_costs:
  total_input_tokens: 910697
  total_output_tokens: 4297
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 910697
      output_tokens: 4297
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 910697
    output_tokens: 4297
    cost_usd: 0.0
    recorded_at: '2026-07-29T21:17:53.194849+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-562__20260729T211610Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-562
    source_sha: 31f8938b8f669a316a830690aaedcc1e0d3834bf
    completed_at: '2026-07-29T21:17:53.207725+00:00'
---
## Summary

Triggered by: OOMPAH-561

Parallel epic integration can deadlock with every submission in Ready to Integrate and attempts=0 when a parent epic branch predates already-Merged finish dependencies. Current claim_next correctly requires dependency code to be reachable from the epic branch, but epic staleness maintenance is observation-only, so no executor or repair agent can make the required base reachable. Live reproduction: OOMPAH-459 is 26 commits behind main/5 ahead and all eight queued children wait on merged OOMPAH-475/467/464/466 ancestry; OOMPAH-460 is 34 behind and all six children wait behind OOMPAH-459. Scope: classify this as the existing synchronization policy's required-base condition; schedule one safe epic rebase/reconciliation action (never direct epic-to-epic sync), prevent duplicate repair dispatch, expose actionable queue/maintenance state, and resume integration after the repaired epic head is published. Preserve explicit finish-order and terminal-audit gates. Relevant files: oompah/orchestrator.py integration queue processing and epic synchronization policy, queue/API status summaries, and focused integration/staleness tests. Acceptance criteria: a Ready queue whose first task depends on merged code absent from its epic branch automatically enters a bounded repair path; after repair, eligible items are claimed in dependency order; no permanent attempts=0 queue remains; failures surface an actionable error without losing private heads; make test passes.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 21:16
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 21:16
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 21:17
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 12
- Tokens: 910.7K in / 4.3K out [915.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 48s
- Log: OOMPAH-562__20260729T211610Z.jsonl
---
author: oompah
created: 2026-07-29 21:18
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 21:18
---
Focus: Maintenance Engineer
---
<!-- COMMENTS:END -->
