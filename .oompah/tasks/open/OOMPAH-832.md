---
id: OOMPAH-832
type: task
status: Open
priority: null
title: Bootstrap terminal-auditor inspection contract onto main
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-831
labels: []
assignee: null
created_at: '2026-08-05T15:52:49.064850Z'
updated_at: '2026-08-05T23:59:24.689796Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 021b424b90fa3b4d4c36d58fb47ac251afa35bc811b0ef3bdeed4c57f7f945bd
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 022512d0-264b-4f79-9d2e-b4e86803e77d
  claim_owner: f7278be4-f84b-419e-8352-94d46afbf29e
  claimed_at: '2026-08-05T23:59:07.262157+00:00'
  claim_expires_at: '2026-08-06T00:29:07.262157+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: a099b545-960f-449a-816b-af0ea096b342
---
## Summary

Triggered by: OOMPAH-831.

The terminal-auditor search/read/git-inspection contract repair is being implemented on the systemic epic OOMPAH-763 branch, but the running server must audit many intermediate tasks before that root can land. After OOMPAH-831 reaches a reviewed Done state, port the same logical repair patch-equivalently onto then-current main as a standalone deployment bootstrap.

Implementation scope:
- Apply only the reviewed OOMPAH-831 tool-contract, bounded-context, safe read-only git classification, prompt/schema, and health-classification changes to current main.
- Reconcile main-only changes without broadening auditor write authority, arbitrary-code execution, network/credential access, path scope, or allowed mutation surface.
- Preserve exact task/audit identity, output bounds, timeout/cancellation behavior, backend parity, and recoverable-versus-fatal denial accounting.

Required tests:
- Run the complete OOMPAH-831 focused auditor/ACP/output/policy/health matrix against the standalone composition.
- Replay the OOMPAH-542 search/read/git-inspection trace and the OOMPAH-815 read-only ref-inspection trace, proving one candidate can reach submit_audit_result without consuming fatal mutation budget.
- Prove arbitrary python -c, redirection, mutation, credential/path escape, process control, and state-changing git remain fatal.
- Run terminal mutation and secret scans plus the configured full Makefile gate.

Acceptance criteria:
- The reviewed standalone head contains no unrelated systemic-epic work and is merged to main.
- A controlled make restart deploys that exact main revision after active agents drain.
- A live terminal audit can use the advertised search/read inspection path without policy-incompatibility health, and no auditor mutation authority is added.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 23:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 23:59
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
