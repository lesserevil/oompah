---
id: OOMPAH-563
type: bug
status: Open
priority: 1
title: Make service-state persistence atomic and recover terminal-audit quarantine
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T21:36:54.712161Z'
updated_at: '2026-07-29T21:39:09.328048Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: bdde81b07a41310991436e518c773d153354bfafae950790f7022c715f28a6f3
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T21:39:05.316495+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Reviewed active OOMPAH-281 and OOMPAH-282, plus closest archived tasks
    OOMPAH-219, OOMPAH-257, and OOMPAH-265. None covers atomic `service_state.json`
    persistence or terminal-audit quarantine recovery. No files or tracker records
    were modified.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: cfb10b58-eddd-4b60-8fc0-76274d98ace6
oompah.task_costs:
  total_input_tokens: 493525
  total_output_tokens: 2600
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 493525
      output_tokens: 2600
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 493525
    output_tokens: 2600
    cost_usd: 0.0
    recorded_at: '2026-07-29T21:39:05.315145+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-563__20260729T213757Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-563
    source_sha: 31f8938b8f669a316a830690aaedcc1e0d3834bf
    completed_at: '2026-07-29T21:39:05.324442+00:00'
---
## Summary

Triggered by: OOMPAH-561

Live terminal-audit enforcement entered quarantine after .oompah/service_state.json was observed malformed twice during concurrent maintenance writes (Expecting ':' delimiter and Extra data). Scope: serialize orchestrator service-state read/modify/write operations with a process-local reentrant lock; write JSON through a same-directory temporary file and atomic replace; preserve and fail closed on an already-unreadable state document instead of overwriting it; keep terminal-audit callback merging compatible; add deterministic concurrent-writer and corrupt-state regression tests; document/verify recovery; and gracefully restart the live service after the tested fix is deployed so the current terminal-task baseline is rebuilt and the alert clears. Relevant files: oompah/orchestrator.py and focused service-state/terminal-audit tests. Acceptance criteria: concurrent paused/cursor/terminal-audit state updates produce one valid document containing every update; a corrupt document is not destroyed; terminal-audit baseline initializes without quarantine after restart; the dashboard alert disappears; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 21:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 21:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 21:39
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 11
- Tokens: 493.5K in / 2.6K out [496.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 16s
- Log: OOMPAH-563__20260729T213757Z.jsonl
---
<!-- COMMENTS:END -->
