---
id: OOMPAH-665
type: task
status: Open
priority: null
title: Retire legacy no-auditor alerts after terminal task completion
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T16:04:07.401588Z'
updated_at: '2026-07-31T18:16:47.175275Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a693eaf278504dc2d35cff16c985f00831ff37d57e34abdc6fd8b491a20c1ccc
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: a5411225-b756-412c-aaaa-590f9d1f5e12
  claim_owner: 5a45ba37-2907-4778-ab15-29d9f2087774
  claimed_at: '2026-07-31T18:16:42.237810+00:00'
  claim_expires_at: '2026-07-31T18:46:42.237810+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: f7c24a87-351c-4edb-917f-4258a546c7b3
---
## Summary

Live reproduction on 2026-07-31 after OOMPAH-653 merged: OOMPAH-644 and OOMPAH-648 are canonically Merged and have owner/pass terminal evidence, but /api/v1/state still emits terminal_audit:no_independent_candidate alerts for audit-710535de2bba and audit-db48e6cb6d3e. Replaying the authorized Merged override for OOMPAH-644 fails HTTP 409 because current evidence differs from the historical override fingerprint, so the supported API cannot retire the stale alert without re-staging an already-terminal task. Implementation scope: during observability reconciliation, treat a no-auditor record as actionable only while it still owns the task's current nonterminal human decision; retire legacy/superseded identities when a later authorized override, PASS, or canonical terminal task state proves they no longer own lifecycle authority, while preserving historical counters and audit records. Do not clear alerts merely because tracker reads fail or evidence is ambiguous. Relevant files include oompah/orchestrator.py terminal-audit observability reconciliation, terminal_transition_coordinator.py retirement metadata, terminal_audit_observability.py, restart recovery, and alert/state tests. Required deterministic tests: migrated pre-fix metadata for OOMPAH-644 override and OOMPAH-648 PASS; changed fingerprint after merge; restart; task reopened with genuinely current no-auditor decision remains actionable; quarantine/read failure fails closed; project isolation. Acceptance: the two stale alerts clear without lifecycle restaging or metadata hand edits, real current Needs Human audit alerts remain, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 18:16
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 18:16
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
