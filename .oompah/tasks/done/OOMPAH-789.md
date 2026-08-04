---
id: OOMPAH-789
type: task
status: Done
priority: 1
title: Add restart and external-failure injection at every workflow boundary
parent: OOMPAH-767
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-790
- OOMPAH-783
labels: []
assignee: null
created_at: '2026-08-04T13:59:14.267846Z'
updated_at: '2026-08-04T18:11:55.948912Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: blocked
  attempts: 1
  task_branch: OOMPAH-789
  base_branch: epic-OOMPAH-767
  head_sha: 6ae941a31682dce6cd9346c3c4d7116a4c2db8ae
  submitted_at: '2026-08-04T18:09:54.391958+00:00'
  updated_at: '2026-08-04T18:10:59.260837+00:00'
  last_error: task worktree head fee2b7a57f1f85b44b82cc23b4e6734d27d5e4d1 differs
    from the published task head 6ae941a31682dce6cd9346c3c4d7116a4c2db8ae; refusing
    to reset a preserved recovery snapshot
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-a472bd66254d
    project_id: proj-14849f1b
    task_id: OOMPAH-789
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 936ecf5bf8338fc12a9b34dd30aa75b29cd93311b67281d69ad085fa3280b7be
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct-owner implementation was fully tested and published at exact head
      6ae941a31682dce6cd9346c3c4d7116a4c2db8ae on epic-OOMPAH-767. Integration incorrectly
      rejected it because the preserved task recovery worktree remained at parent
      head fee2b7a57f1f85b44b82cc23b4e6734d27d5e4d1.
    created_at: '2026-08-04T18:11:46.474470+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-789
    target_state: Done
    evidence_fingerprint: 936ecf5bf8338fc12a9b34dd30aa75b29cd93311b67281d69ad085fa3280b7be
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-04T18:11:54.728185+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Create controllable fault hooks/test adapters for process death or exception before/after job enqueue, lease, revalidation, Git/forge effect, tracker mutation, verification, transition journaling, and completion. Inject stale/missing tracker snapshots, duplicate/dropped events, fetch failure, deleted branches, target/head changes, expired leases, auth/policy changes, transport failures, and concurrent API/scheduler intents. Use real temporary SQLite, native Markdown trackers, and Git repositories. Acceptance: each boundary has a deterministic restart test; recoverable faults converge after restart; unrecoverable faults become bounded action_required without unsafe mutation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 18:09
---
Implemented typed, deterministic, serializable one-shot fault scripts covering both sides of all eight workflow boundaries, with adapters for the real job store, action handlers, transition journal, native tracker, snapshots, event delivery, authority, leases, and Git refs. Tests inject restart, stale/missing/fetch/transport, duplicate/drop, deleted/moved branch, auth/policy, lease, and concurrency faults. Verification: 43 new tests and 238 composed workflow tests pass; Ruff, terminal scan, and secret scan pass. Exact pushed head: 6ae941a31.
---
author: oompah
created: 2026-08-04 18:10
---
Added deterministic boundary and external-failure injection harness at 6ae941a31.
---
author: oompah
created: 2026-08-04 18:11
---
Integration could not verify `OOMPAH-789`: task worktree head fee2b7a57f1f85b44b82cc23b4e6734d27d5e4d1 differs from the published task head 6ae941a31682dce6cd9346c3c4d7116a4c2db8ae; refusing to reset a preserved recovery snapshot

Fetch the private branch, preserve its commits, push a clean current head, and submit it again.
---
author: oompah
created: 2026-08-04 18:11
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct-owner implementation was fully tested and published at exact head 6ae941a31682dce6cd9346c3c4d7116a4c2db8ae on epic-OOMPAH-767. Integration incorrectly rejected it because the preserved task recovery worktree remained at parent head fee2b7a57f1f85b44b82cc23b4e6734d27d5e4d1.
---
<!-- COMMENTS:END -->
