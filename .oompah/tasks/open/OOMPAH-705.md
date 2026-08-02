---
id: OOMPAH-705
type: bug
status: Open
priority: 1
title: Fetch an accepted submission head before standalone review gating
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T21:30:29.609691Z'
updated_at: '2026-08-02T21:51:45.765288Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9022b41abb779a660b1286993c3e62e509999d8ccc4856fcec48a9ffbcd1a4a8
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 253e9696-abbe-40da-9c53-1db159b6d476
  claim_owner: 0b22eab2-a2d1-4082-a6c8-404ec37650a4
  claimed_at: '2026-08-02T21:51:36.474572+00:00'
  claim_expires_at: '2026-08-02T22:21:36.474572+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3c09c281-63ea-4db7-a10f-52faf4d9efcd
---
## Summary

Triggered by: OOMPAH-704

Production regression of OOMPAH-700: OOMPAH-704 was submitted from a clean non-canonical worktree with branch OOMPAH-704 and exact head 5640fc49e3036e552d4c047c9c35b6509e94e8cd. The API accepted and persisted integration.task_branch and integration.head_sha, and origin/OOMPAH-704 existed at that SHA, but _review_quality_gate_passes called _quality_gate_branch_head against project.repo_path (/home/shedwards/.oompah/repos/oompah) before fetching the newly pushed ref. Because that managed clone lacked refs/remotes/origin/OOMPAH-704, review gating reported Head: unknown and infrastructure_error without running CI. Implementation scope: bind the gate to the persisted submitted head SHA; fetch/materialize that exact object/ref into the managed repository when absent, with bounded authenticated git operations and clear infrastructure errors; verify the fetched branch tip still equals integration.head_sha before running; preserve branch-advancement fencing and never silently substitute a newer remote head. Avoid requiring an operator fetch or a surviving canonical worktree. Add regression tests where the remote branch is pushed after the managed clone's last fetch, exact SHA fetch succeeds, remote tip differs from submitted head, commit is unavailable, repeated recovery is idempotent, and no CI-fix label is added for fetch infrastructure failures. Acceptance criteria: the OOMPAH-704 reproduction gates 5640fc49e without manual fetch; OOMPAH-700's non-canonical submission promise holds across stale managed clones; focused exact-head/standalone submission tests, terminal mutation scan, and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 21:51
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-02 21:51
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
