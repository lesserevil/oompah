---
id: OOMPAH-1001
type: bug
status: Backlog
priority: 1
title: Import trusted protected recovery-PR exact-head gates before terminal-audit
  dispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T17:36:35.101810Z'
updated_at: '2026-08-10T17:36:35.101810Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: o999-protected-recovery-pr-gate-import-v1
  request_fingerprint: ea272e3261553b0afbf6159e7cf5993e453800bc18863cb9a23339b827c4abb9
---
## Summary

Triggered by: OOMPAH-999

Triggered by OOMPAH-999. Problem: recovery head 6418a935de7b4aab93a24af4756a54b344463513 passed the complete local Makefile gate and protected PR #799 Python 3.11/3.12/3.13 checks, but no exact evidence entered quality_gates.json, so terminal audit redundantly launched make test until a supported owner override. Scope: in oompah/scm.py expose rich exact-SHA check/workflow evidence including check/run IDs, head SHA, workflow identity, run attempt, status, and conclusion; in oompah/quality_gate.py add a fail-closed imported/attested PASS API with durable provenance while retaining the repo/target/source/exact-head/configured-command key; in oompah/orchestrator.py import evidence during merged recovery-review reconciliation before auditor dispatch only when current audit binding, PR source/head/base, target containment, and configured command all agree. Document operator trust configuration in docs/operator-runbook.md if needed. Never translate aggregate CIStatus passed directly: require exact PR head, merged target, every configured required context/matrix job successful, and trusted workflow/command attestation proving the protected workflow ran test_command_full. Reject empty, neutral, skipped, cancelled, altered, wrong-SHA/base/source, stale attempt/fingerprint, degraded API, replayed, or advanced-head evidence. Tests: PR #799-shaped evidence imports one durable PASS and the first auditor reuses it without launching a full command, including after restart; every trust mismatch runs the ordinary full gate; concurrent import/dispatch is idempotent; serialized provenance cannot be reused across repo, branch, head, or command. Acceptance: authoritative protected recovery-PR gates are reused exactly once without weakening fail-closed terminal audit behavior, and focused plus complete protected gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

