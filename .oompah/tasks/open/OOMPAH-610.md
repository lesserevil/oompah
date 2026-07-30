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
updated_at: '2026-07-30T18:54:00.263849Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: bc294a0c7385189335b6f506d2ae07b096e00f7fb10f230cc9acd1e7494ff87f
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 198d1e1b-ff70-42f1-ad48-0c729bad2a17
  claim_owner: ac40770c-37a8-4b2c-b040-7a7ae948f467
  claimed_at: '2026-07-30T18:53:56.485776+00:00'
  claim_expires_at: '2026-07-30T19:23:56.485776+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 4db1411f-cfb9-4104-bba9-bc0122ff5e83
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
<!-- COMMENTS:END -->
