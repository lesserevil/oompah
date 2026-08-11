---
id: OOMPAH-1080
type: task
status: Backlog
priority: null
title: Import trusted protected ordinary-PR exact-head gates before terminal-audit
  dispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T11:00:26.321021Z'
updated_at: '2026-08-11T11:00:26.321021Z'
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
  creation_marker: ac7161fc-9c77-4b8e-aa7b-5686df38ab4b
  request_fingerprint: 2bf5c669d1b5f34c19c01be0a65e261135dfea89635e99fb0c368010765c3a6f
---
## Summary

Triggered by: OOMPAH-1071. Problem: OOMPAH-1071 final reviewed head 238736... differed from its earlier local gate head baa287..., yet protected PR 810 had passed the pinned Python 3.11/3.12/3.13 matrix and merged exactly. Terminal audit did not import that ordinary PR evidence, reran the full Makefile gate for more than 15 minutes, serialized validation, and delayed graceful deployment. OOMPAH-1001 imports only recovery-PR evidence. Scope: generalize the existing strict protected-evidence importer to ordinary merged PRs before terminal-audit dispatch, retaining exact project/repo/source/head/base/target-containment/configured-command/workflow-blob/job/app/attempt/trust-fingerprint checks and fail-closed behavior. Never consume aggregate CI status, synthetic merge evidence without the existing exact-head/tree attestation, partial/skipped/neutral/cancelled jobs, stale attempts, advanced heads, wrong base/source, degraded API, or changed trust configuration. Relevant code: oompah/scm.py, oompah/quality_gate.py, oompah/orchestrator.py and terminal-audit launch/reconciliation tests. Tests/acceptance: an OOMPAH-1071/PR810-shaped ordinary merged PR imports one durable exact-head PASS and the first audit reuses it without launching make test, including after restart; stale/wrong/replayed/concurrent evidence fails closed or is idempotent; recovery PR behavior remains green; protected CI and focused tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

