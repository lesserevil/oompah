---
id: OOMPAH-1261
type: task
status: In Validation
priority: null
title: Recover Ready-to-Integrate work when the remote review head advances past the
  accepted submission
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-14T01:17:47.268102Z'
updated_at: '2026-08-14T03:21:16.760145Z'
work_branch: OOMPAH-1261
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 5cf07b32-4562-410f-b82c-de37c40187c0
  request_fingerprint: 1a91df46d5640339a0e28cc8b1c15a2ac70f7a10c937d3194305fd4c9011d4a0
oompah.lifecycle_revision: 2
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1261
  base_branch: main
  base_sha: 5a0ae9f886796123d6a7a1dd095f6b823fb4cd7f
  head_sha: ee95f1e9f5e7d632c1e12c91870e96ebb5ff36f4
  submitted_at: '2026-08-14T03:02:42.864361+00:00'
  updated_at: '2026-08-14T03:02:42.864361+00:00'
oompah.work_branch: OOMPAH-1261
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-2fffd6e870fa
    project_id: proj-14849f1b
    task_id: OOMPAH-1261
    digest: d80e5755eb28e942ed5aa9b73deab29bc876814f3c7c5c1cd20c08a54493bc46
  - version: 1
    audit_id: audit-d1141d6cec50
    project_id: proj-14849f1b
    task_id: OOMPAH-1261
    digest: d80e5755eb28e942ed5aa9b73deab29bc876814f3c7c5c1cd20c08a54493bc46
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-2fffd6e870fa
    project_id: proj-14849f1b
    task_id: OOMPAH-1261
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d80e5755eb28e942ed5aa9b73deab29bc876814f3c7c5c1cd20c08a54493bc46
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-14T03:06:31.579686+00:00'
    eligible_at: '2026-08-14T03:06:31.579686+00:00'
    selected_ref: ee95f1e9f5e7d632c1e12c91870e96ebb5ff36f4
    selected_sha: ee95f1e9f5e7d632c1e12c91870e96ebb5ff36f4
  - version: 1
    audit_id: audit-d1141d6cec50
    project_id: proj-14849f1b
    task_id: OOMPAH-1261
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d80e5755eb28e942ed5aa9b73deab29bc876814f3c7c5c1cd20c08a54493bc46
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-14T03:06:31.579686+00:00'
    prerequisite_audit_id: audit-2fffd6e870fa
    selected_ref: ee95f1e9f5e7d632c1e12c91870e96ebb5ff36f4
    selected_sha: ee95f1e9f5e7d632c1e12c91870e96ebb5ff36f4
  attempt_history: []
---
## Summary

Bug reproduced by TRICKLE-136: the accepted integration submission records head 835ae436 while the remote task branch and open MR !19 point at fea95f19. standalone_delivery keeps evaluating the stale accepted head, exhausts 5/5 attempts, and cannot naturally return the task to a truthful resubmission flow. Scope: in the Ready to Integrate / standalone delivery path, compare the accepted integration head with the authoritative current remote task-branch and review head; when they differ, durably retire the stale delivery generation without consuming retry budget, expose a precise resubmission-required disposition for the newer head, and converge after an exact-head resubmission. Preserve fail-closed behavior for ambiguous/missing remote identity and do not silently adopt unsubmitted code. Relevant areas include standalone delivery, integration fact collection, submitted-head authority, recovery projections, and restart reconstruction. Add regressions for remote branch/MR head advance after accepted submission, unchanged exact head, missing/ambiguous remote identity, concurrent resubmission race, retry-budget preservation, and restart recovery. Acceptance: TRICKLE-136 can be worked around by exact-head resubmission and then flows naturally; future drift does not exhaust standalone delivery against a known-stale head; diagnostics name accepted and observed heads; focused/full CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 01:18
---
Filed from the live TRICKLE-136 audit after confirming no existing task covers this exact Ready-to-Integrate accepted-head drift. Closest prior fixes address different lifecycle cuts and intentionally retain mismatched-head fences.
---
author: oompah
created: 2026-08-14 01:35
---
Claimed for direct implementation while OOMPAH-1260 exact-head CI runs. Working branch/worktree: OOMPAH-1261 at /home/shedwards/src/oompah-1261. Oompah project remains paused; no service scheduling is being used.
---
author: oompah
created: 2026-08-14 01:38
---
Correction from exact live audit: TRICKLE-136's current review is GitLab MR !14, not !19. Accepted head is 835ae43684ab47660a77e2a04a10b414a0f0181d; remote branch and MR !14 head are fea95f192d66fbf07f0188ad632e42c0ceb21d52. The heads diverge. The MR is open, non-draft, conflict-free, and pending only on the required offline macOS runner.
---
author: oompah
created: 2026-08-14 01:40
---
Live in-flight workaround completed safely while Trickle remained paused: a fresh exact-head clone verified branch and MR !14 at fea95f192d66fbf07f0188ad632e42c0ceb21d52,  rebound TRICKLE-136, and the server detail now confirms ready/standalone authority at that exact head. The temporary clone was moved to trash. This unblocks the existing task after resume; OOMPAH-1261 remains required to prevent retry exhaustion before explicit resubmission.
---
author: oompah
created: 2026-08-14 01:40
---
Clarification: the successful operator action was oompah task submit for TRICKLE-136 from the fresh exact-head clone. No worker handoff credential or stale managed worktree was used.
---
author: oompah
created: 2026-08-14 02:16
---
Implementation frozen at commit 41bdebc829fcd1bb5e3a7957f671961bbf5ff33c. Accepted-versus-remote authority is projected before scheduling; advanced heads require explicit exact-head resubmission; unavailable identity is truthfully jobless/blocked; proven late drift supersedes without consuming retry budget; and stale review-cache data cannot deadlock an exact authoritative branch. Independent authority/race review found no silent-adoption path after two blockers were corrected. Focused suite passes 488 tests; full Makefile gate is running on the exact commit.
---
author: oompah
created: 2026-08-14 03:02
---
Implemented authoritative remote-head recovery for Ready to Integrate work, including exact-head resubmission decisions, fail-closed ambiguity handling, stale-cache protection, typed late-drift supersession, and regression coverage. Exact pushed head ee95f1e9f5e7d632c1e12c91870e96ebb5ff36f4 is under GitHub PR 878 with auto-merge enabled; all focused checks pass and the full CI matrix is running.
---
author: oompah
created: 2026-08-14 03:06
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 03:21
---
Acceptance complete: PR 878 merged after all Python 3.11/3.12/3.13 CI lanes passed. Main and the running service are at 948ef6f207eabe4c26910d8fc276d6d36b659e76. Live TRICKLE-136 now remains In Review on exact tracker/MR head fea95f192d66fbf07f0188ad632e42c0ceb21d52; its older retained worktree is non-authoritative and no stale standalone-delivery job is active. The OOMPAH-1261 worktree plus local/remote branches were pruned.
---
<!-- COMMENTS:END -->
