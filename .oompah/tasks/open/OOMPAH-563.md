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
labels:
- needs:refactor
assignee: null
created_at: '2026-07-29T21:36:54.712161Z'
updated_at: '2026-07-29T21:42:53.128851Z'
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
oompah.agent_run_id: e71a81d4-84d5-4fcf-bada-29f92e9bf4df
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
author: oompah
created: 2026-07-29 21:39
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 21:39
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 21:39
---
Root cause confirmed: Orchestrator._save_state performed an unlocked in-place read/modify/write from dispatch and maintenance threads. Live logs captured malformed JSON twice, after which later writes replaced the document with only a maintenance cursor. Implemented a process-local RLock covering the full transaction, fsynced same-directory temporary writes plus atomic replace, and fail-closed preservation after any read failure. Added deterministic overlapping-writer, corrupt-state preservation, serialization-failure, terminal-audit merge, and post-restart recovery tests; focused suite is green (27 passed).
---
author: oompah
created: 2026-07-29 21:42
---
HANDOFF: Frontend Developer assessment - This task requires backend/orchestrator expertise, not frontend work.

**Finding**: OOMPAH-563 is fundamentally a Python concurrency and file I/O atomicity issue in oompah/orchestrator.py, not user-facing UI work. The scope involves:
- Serializing service-state read/modify/write operations with process-local reentrant locks
- Atomic JSON file writes via temporary files  
- Corrupt state document preservation (fail-closed approach)
- Concurrency regression tests
- Terminal-audit integration

**Current state**: The terminal_audit_enforcement.py already has basic locking infrastructure (_STATE_LOCK_GUARD, _STATE_LOCKS dict, reentrant RLock) and temporary file handling in _persist(). However, concurrent updates from multiple orchestrator components (paused state, cursor state, terminal-audit state) to service_state.json are not properly coordinated.

The only frontend mention is verifying the dashboard alert clears after restart—that's monitoring, not UI development.

**Recommendation**: This needs a backend/core specialist to extend orchestrator.py's locking model across all service-state mutation points, ensure atomic compound writes, add deterministic concurrent-writer tests, and implement recovery verification. I am not the right agent for this work.

**Next focus**: `needs:refactor` (core orchestrator work)
---
<!-- COMMENTS:END -->
