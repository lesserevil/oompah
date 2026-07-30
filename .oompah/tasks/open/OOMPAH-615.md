---
id: OOMPAH-615
type: bug
status: Open
priority: 1
title: Fence implementation retries when terminal audits take ownership
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T20:22:18.934506Z'
updated_at: '2026-07-30T20:23:34.422379Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1ffadb7c497f76972b5542efce9941a262600258b9584273d2e08e0924a8c309
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 48b89e54-bd24-4eed-9120-ca454b1913d2
  claim_owner: c1f4a4cb-217d-4c2a-aad6-f768a3cdbb4b
  claimed_at: '2026-07-30T20:23:27.676000+00:00'
  claim_expires_at: '2026-07-30T20:53:27.676000+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: fa59bec8-25c5-4058-af04-534658aa328c
---
## Summary

Triggered by: OOMPAH-591

Implementation scope: Fix the reproduced ownership races between ordinary worker retries and terminal-audit dispatch. A supported Done request that stages a task in In Validation must request an immediate scheduler refresh. The same transition must atomically invalidate every pending, delayed, or callback-owned implementation retry before auditor ownership becomes visible, and a retry callback must re-read canonical task state immediately before dispatch so it cannot reopen or reclaim In Validation, Done, Merged, Archived, or Needs Human work. Preserve ordinary retry behavior for genuinely In Progress/Open work and keep auditor retry rotation independent. Relevant files include oompah/server.py terminal transition handling, oompah/orchestrator.py retry scheduling/callback and dispatch events, and related state snapshots. Tests: deterministically reproduce (1) terminal audit staged between worker exit and delayed retry callback, (2) callback already awakened while the terminal transition cancels ownership, (3) In Validation staging wakes the audit lane without waiting for the safety-net poll, and (4) normal retries still dispatch. Assert there is never simultaneous implementation/auditor ownership and task state cannot regress from In Validation to In Progress/Open. Run focused server/orchestrator/auditor tests and make test. Acceptance criteria: staged audits wake immediately; terminal transition wins every implementation-retry race; no stale implementation agent can launch after audit staging; live OOMPAH-591 can be requeued and receive exactly one auditor; all tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 20:22
---
Claimed directly by the operator Codex session after live reproduction on OOMPAH-591. I will implement and verify this task locally; do not dispatch a separate implementation agent.
---
author: oompah
created: 2026-07-30 20:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 20:23
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
