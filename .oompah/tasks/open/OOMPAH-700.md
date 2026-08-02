---
id: OOMPAH-700
type: bug
status: Open
priority: 1
title: Gate accepted submissions without a canonical task worktree
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T19:52:39.323644Z'
updated_at: '2026-08-02T19:56:31.406090Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d7674744c97e28ac82f72e0612635fd532dc44d1a9094bb4fbf95b21aa9eecfe
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 0ea15e70-7694-40c4-8a14-24d19f40aa8d
  claim_owner: 16260a3a-9797-4dbe-a807-70529a91a50b
  claimed_at: '2026-08-02T19:56:24.059113+00:00'
  claim_expires_at: '2026-08-02T20:26:24.059113+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9bf00797-340c-478f-b549-884a22087b69
---
## Summary

Triggered by: OOMPAH-698

Production reproduction from OOMPAH-698: oompah task submit accepted a clean, pushed checkout whose branch and exact head matched the task, but the standalone review gate only searched the canonical managed worktree path and project checkout. It then moved the task to Needs CI Fix with No existing worktree matched the review branch tip, despite the submitted head already being available at origin/OOMPAH-698 and having passed the full gate in the submitting checkout.\n\nImplementation scope:\n- Make exact-head review gating independent of a surviving checkout at the submitted branch head. Materialize or snapshot the verified remote/local ref from the managed repository, or reject unsupported submission locations synchronously before returning success.\n- Preserve the immutable exact-head sandbox, lifecycle safety-head containment, clean-tree guarantees, generation cancellation, and cache semantics.\n- Do not trust a client-supplied filesystem path and do not require operators to copy an otherwise valid checkout into the private worktree directory.\n- Classify missing commit objects or unavailable remote refs as infrastructure/evidence failures, not candidate CI failures; never add ci-fix for a gate command that did not run.\n- Make retries and restart recovery idempotent.\n\nRelevant code: oompah/orchestrator.py quality-gate worktree discovery and review gate; oompah/quality_gate.py exact-head snapshot/preflight; submission validation in oompah/server.py and oompah/task_cli.py.\n\nRequired tests:\n- A valid pushed submission from a clean non-canonical checkout gates the exact remote head and creates a review.\n- A missing canonical worktree does not become Needs CI Fix when the exact commit exists in the managed repository.\n- A missing or unfetchable exact head fails closed with an actionable infrastructure classification and no ci-fix label.\n- A branch advancing during snapshot or gate remains stale and cannot create a review.\n- Repeated resubmission and restart runs at most one gate per evidence key and one review.\n\nAcceptance criteria:\n- The OOMPAH-698 reproduction completes without manually recreating its worktree.\n- Accepted submissions cannot be stranded solely by checkout-path discovery.\n- Focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 19:56
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-02 19:56
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
