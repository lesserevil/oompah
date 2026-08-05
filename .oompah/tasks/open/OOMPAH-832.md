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
updated_at: '2026-08-05T15:52:56.285935Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
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

