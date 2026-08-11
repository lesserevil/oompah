---
id: OOMPAH-1080
type: task
status: In Review
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
updated_at: '2026-08-11T11:39:17.202787Z'
work_branch: OOMPAH-1080
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/818
review_number: '818'
review_head: eabbcdaceabad696070014a6fa166c8d1334f46a
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: ac7161fc-9c77-4b8e-aa7b-5686df38ab4b
  request_fingerprint: 2bf5c669d1b5f34c19c01be0a65e261135dfea89635e99fb0c368010765c3a6f
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1080
  head_sha: eabbcdaceabad696070014a6fa166c8d1334f46a
  submitted_at: '2026-08-11T11:27:23.712478+00:00'
  updated_at: '2026-08-11T11:27:23.712478+00:00'
oompah.work_branch: OOMPAH-1080
oompah.review_url: https://github.com/lesserevil/oompah/pull/818
oompah.review_number: '818'
oompah.target_branch: main
oompah.review_head: eabbcdaceabad696070014a6fa166c8d1334f46a
---
## Summary

Triggered by: OOMPAH-1071. Problem: OOMPAH-1071 final reviewed head 238736... differed from its earlier local gate head baa287..., yet protected PR 810 had passed the pinned Python 3.11/3.12/3.13 matrix and merged exactly. Terminal audit did not import that ordinary PR evidence, reran the full Makefile gate for more than 15 minutes, serialized validation, and delayed graceful deployment. OOMPAH-1001 imports only recovery-PR evidence. Scope: generalize the existing strict protected-evidence importer to ordinary merged PRs before terminal-audit dispatch, retaining exact project/repo/source/head/base/target-containment/configured-command/workflow-blob/job/app/attempt/trust-fingerprint checks and fail-closed behavior. Never consume aggregate CI status, synthetic merge evidence without the existing exact-head/tree attestation, partial/skipped/neutral/cancelled jobs, stale attempts, advanced heads, wrong base/source, degraded API, or changed trust configuration. Relevant code: oompah/scm.py, oompah/quality_gate.py, oompah/orchestrator.py and terminal-audit launch/reconciliation tests. Tests/acceptance: an OOMPAH-1071/PR810-shaped ordinary merged PR imports one durable exact-head PASS and the first audit reuses it without launching make test, including after restart; stale/wrong/replayed/concurrent evidence fails closed or is idempotent; recovery PR behavior remains green; protected CI and focused tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 11:27
---
Generalize strict protected exact-head gate import from recovery PRs to ordinary merged PRs at eabbcdaceabad696070014a6fa166c8d1334f46a; 294 focused quality-gate tests and terminal scan pass.
---
author: oompah
created: 2026-08-11 11:35
---
Independent exact-head review ACCEPT for eabbcdaceabad696070014a6fa166c8d1334f46a. Reviewer verified remote/head identity, ordinary and recovery protected-evidence boundaries, provider/job/attempt/app/workflow/tree trust binding, replay and revocation behavior, and no aggregate-CI fallback. Independent tests: 294 quality-gate tests and 12 strict protected-workflow provider tests passed.
---
author: oompah
created: 2026-08-11 11:38
---
Branch quality gate passed for `eabbcdaceabad696070014a6fa166c8d1334f46a` using `make test` in 196.8s. Review creation may proceed.
---
<!-- COMMENTS:END -->
