---
id: OOMPAH-610
type: bug
status: Open
priority: 1
title: Release stale claimed_issues entries when completion auditors exit
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T18:53:05.632137Z'
updated_at: '2026-07-30T19:00:37.257580Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: bc294a0c7385189335b6f506d2ae07b096e00f7fb10f230cc9acd1e7494ff87f
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T18:58:45.299450+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Reviewed active OOMPAH-591, OOMPAH-592, OOMPAH-593, and OOMPAH-599.
    None covers completion-auditor exit cleanup of `state.claimed_issues` and audit-branch
    claims. OOMPAH-590 is the closest predecessor but is terminal (`Done`) and excluded.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 7cfdf01f-b254-4b46-bd7b-9c752596fcaf
oompah.task_costs:
  total_input_tokens: 2400319
  total_output_tokens: 10074
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 2400319
      output_tokens: 10074
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 2400319
    output_tokens: 10074
    cost_usd: 0.0
    recorded_at: '2026-07-30T18:58:45.298050+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-610__20260730T185400Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-610
    source_sha: b4fa5db81322ae24b90a5c80689d94d1a49a1f30
    completed_at: '2026-07-30T18:58:45.304450+00:00'
---
## Summary

Triggered by: OOMPAH-590

Implementation scope: Fix the completion-auditor worker-exit path in oompah/orchestrator.py so every auditor exit removes the issue from both state.claimed and state.claimed_issues, releases its audit branch claim, and leaves the pending terminal-audit request eligible for candidate rotation or explicit no-auditor routing after backoff. Preserve ordinary-worker and duplicate-preflight cleanup behavior. Add defensive observability or invariant coverage if needed so a stale in-memory claim cannot silently suppress an In Validation request forever.\n\nRequired tests: Add a regression reproducing an auditor that exits stalled or errored without a structured result, then prove _audit_branch_busy is false after cleanup and the next audit-lane tick either dispatches the next independent candidate or routes exhaustion to Needs Human. Cover idempotent cleanup and retain existing auditor dispatch tests. Run focused scheduler/auditor tests and make test.\n\nAcceptance criteria: No ended auditor remains in state.claimed_issues; OOMPAH-593 and equivalent In Validation tasks cannot be silently skipped after retry_after; the scheduler reaches a new auditor or an actionable terminal outcome; all relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 18:53
---
Claimed by the interactive operator session for immediate self-hosting recovery. Root cause reproduced on OOMPAH-593: auditor exit clears state.claimed and the branch claim but leaves state.claimed_issues, causing _audit_branch_busy to suppress every retry after next_retry_at.
---
author: oompah
created: 2026-07-30 18:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 18:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 18:55
---
Implemented locally: auditor exit now removes state.claimed_issues in addition to state.claimed and the audit branch claim. The audit branch gate also prunes orphaned claimed_issues entries whose ID is absent from state.claimed, with a warning, while preserving active claim serialization. Added focused regressions for stalled auditor cleanup and defensive stale-claim pruning. Focused auditor/terminal suites: 298 passed; full gate next.
---
author: oompah
created: 2026-07-30 18:58
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 27
- Tokens: 2.4M in / 10.1K out [2.4M total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 47s
- Log: OOMPAH-610__20260730T185400Z.jsonl
---
author: oompah
created: 2026-07-30 18:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 18:59
---
Focus: Refactoring Specialist
---
<!-- COMMENTS:END -->
