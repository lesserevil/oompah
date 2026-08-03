---
id: OOMPAH-711
type: bug
status: Open
priority: null
title: Fence owner duplicate resolution from superseded preflight exit
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T23:59:03.600915Z'
updated_at: '2026-08-03T00:05:02.619594Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 202c56bf80474585cba587c717a0651c36dc9fd09908afc88a9cb21caf68b2d2
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: ebca466d-acdf-4938-974a-34d79f40d51c
  claim_owner: 282fbdbd-517c-4b57-a6ee-f47cdefb1b24
  claimed_at: '2026-08-03T00:05:00.935144+00:00'
  claim_expires_at: '2026-08-03T00:35:00.935144+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

Triggered by: OOMPAH-710; regression of OOMPAH-682 and OOMPAH-535.

Live reproduction on 2026-08-02: OOMPAH-710 had a third duplicate-preflight worker active after two inconclusive contract failures. The authenticated project-owner resolution endpoint successfully recorded no_duplicate, reset retry_count to 0, and returned the task to Open. The owner then added human-only and moved the task to In Progress for direct implementation. After the superseded duplicate worker exited and the service later auto-updated, OOMPAH-710 surfaced as Done despite an uncommitted dirty implementation worktree and no task submit. The task had to be reopened manually. This violates OOMPAH-682 acceptance that late claim completion cannot overwrite a newer owner resolution or task revision.

Implementation scope:
- Make owner-resolution acquire/revoke the exact duplicate claim generation atomically and cancel/await any active matching preflight before returning success, or persist a generation tombstone that the exit path must honor.
- Make duplicate-preflight normal/cancelled/forced exit compare the current task fingerprint, owner-resolution generation, claim identity, and status before any tracker transition or completion bookkeeping.
- Never infer implementation completion/Done from a duplicate-investigator exit.
- Preserve the newer owner-selected Open/In Progress state and human-only ownership across graceful restart and auto-update.
- Keep visible agent/process lifecycle truthful while the superseded preflight is terminating.

Relevant code: duplicate owner-resolution route in oompah/server.py; duplicate claim/finish and worker-exit paths in oompah/orchestrator.py; oompah/duplicate_screening.py metadata generations; restart recovery covered by OOMPAH-701/704/707.

Required tests:
- Barrier-race a live duplicate worker exit against owner no_duplicate resolution, then move the task to In Progress and prove late output/exit cannot change status or retry metadata.
- Repeat with cancellation-resistant provider termination and prove the endpoint does not retire visibility before the process exits.
- Restart between owner resolution and old worker exit and prove the owner-selected state survives exactly once.
- Assert a duplicate-preflight exit can never set Done or submit implementation work.
- Focused duplicate owner/claim tests and make test/check-secrets pass.

Acceptance criteria:
- Owner-resolution success is a generation fence: every older preflight result and exit becomes a no-op except bounded cleanup.
- Direct owner work cannot be marked Done, reopened, or redispatched by the superseded investigator.
- The OOMPAH-710 sequence is deterministic and leaves no hidden provider, phantom claim, or tracker-state regression.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

