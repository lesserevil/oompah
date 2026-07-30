---
id: OOMPAH-590
type: bug
status: Open
priority: 1
title: Retry terminal audits after auditor launch or transport failure
parent: OOMPAH-585
children: []
blocked_by:
- OOMPAH-589
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:22.194798Z'
updated_at: '2026-07-30T14:20:53.088186Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-590
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 668767bd8dc2d7a2894cecc5ec77ed49df140e098ac2791ef421df1d1e9f916c
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 5181b5f6-d3d9-4b7b-afc0-a9cad3ce317f
  claim_owner: 9e3a680b-e68a-4d5a-ba2e-f9091834f9ec
  claimed_at: '2026-07-30T14:20:44.878946+00:00'
  claim_expires_at: '2026-07-30T14:50:44.878946+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 0ec70f19-d33b-4f1a-a892-a332b5a1d659
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-590
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-590
  base_branch: epic-OOMPAH-585
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T14:20:49.754823+00:00'
---
## Summary

Implementation scope

Treat completion-auditor launch, malformed endpoint, transport, timeout, and provider-session failures as recoverable audit-attempt outcomes. Persist a safe failure classification, release the candidate claim, retry with bounded backoff and the next eligible independent candidate, and prevent duplicate concurrent attempts for one audit/evidence fingerprint. Preserve terminal-state idempotency and audit history. Relevant files include oompah/auditor_dispatch.py, oompah/terminal_transition_coordinator.py, orchestrator audit dispatch/reconciliation, and state metadata.

Tests

Cover launch exception, transport exception, timeout, next-candidate fallback, exhausted candidates, restart recovery, duplicate tick coalescing, and successful later completion. Run focused terminal/auditor tests and make test.

Acceptance criteria

A transient auditor-session failure cannot leave a request silently Pending forever; the request either passes on retry or reaches an explicit actionable exhausted/needs-human state.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 14:20
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 14:20
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
