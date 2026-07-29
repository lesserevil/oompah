---
id: OOMPAH-475
type: feature
status: In Progress
priority: 1
title: Dispatch, retry, and recover independent auditor agents
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-464
- OOMPAH-465
- OOMPAH-466
- OOMPAH-468
- OOMPAH-469
- OOMPAH-470
- OOMPAH-471
- OOMPAH-472
- OOMPAH-473
- OOMPAH-474
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:15.927352Z'
updated_at: '2026-07-29T14:34:51.384596Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0f24e8e01a09c697f39206579599cd6c6686fb4e0022d352835b5a8cfcc1eaef
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:26:16.084248+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \nEvidence: Searched `.oompah/tasks`, docs, and plans. Active\
    \ tasks OOMPAH-281 and OOMPAH-282 cover unrelated CI runner and migration-error\
    \ work. Audit-related records are archived or design documentation and were excluded.\
    \ No files or tracker state were modified."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: fb866520-a3d5-4744-9e04-88bd1a0b36ce
oompah.work_branch: epic-OOMPAH-458
oompah.task_costs:
  total_input_tokens: 409050
  total_output_tokens: 2858
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 409050
      output_tokens: 2858
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 409050
    output_tokens: 2858
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:26:16.083625+00:00'
---
## Summary

Implementation scope

Add a priority audit lane that reads persisted In Validation requests, gathers target-specific evidence, selects an independent candidate, claims the task/epic branch, and starts the reserved auditor focus. Auditors consume the normal global concurrency limit and serialize with implementation workers on the same task or epic branch. Persist running attempt identity before launch. On transient provider/tool failure, rotate candidates with normal backoff up to OOMPAH_AUDIT_MAX_ATTEMPTS. Rehydrate pending/running attempts on restart, detect abandoned auditor sessions, and retry idempotently. If every independent candidate is exhausted, submit the no-independent-auditor failure so the coordinator moves to Needs Human with configuration instructions.

Tests

Cover priority versus ordinary Open work, concurrency limit, one-agent-per-epic serialization, successful result, candidate rotation, rate limit, timeout, crash, restart, abandoned claim, changed fingerprint during run, stale result, max attempts, no candidates, and actionable final comment. Run focused scheduler tests and make test.

Acceptance criteria

Every eligible persisted audit is eventually dispatched once, retried safely, or moved to actionable Needs Human; auditor work never races a branch writer or exceeds configured global concurrency.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:25
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:26
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 8
- Tokens: 409.1K in / 2.9K out [411.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 15s
- Log: OOMPAH-475__20260729T012510Z.jsonl
---
author: oompah
created: 2026-07-29 14:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 14:34
---
Focus: Technical Writer
---
<!-- COMMENTS:END -->
