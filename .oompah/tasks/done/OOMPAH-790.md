---
id: OOMPAH-790
type: feature
status: Done
priority: 1
title: Build a stateful reference model and generative workflow harness
parent: OOMPAH-767
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-772
labels: []
assignee: null
created_at: '2026-08-04T13:59:16.097978Z'
updated_at: '2026-08-04T17:59:49.280419Z'
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
  task_branch: OOMPAH-790
  base_branch: epic-OOMPAH-767
  base_sha: fee2b7a57f1f85b44b82cc23b4e6734d27d5e4d1
  head_sha: fee2b7a57f1f85b44b82cc23b4e6734d27d5e4d1
  submitted_at: '2026-08-04T17:57:59.423194+00:00'
  updated_at: '2026-08-04T17:59:07.672221+00:00'
  last_error: epic worktree head a681ec2fc005f339063b3b8e2a139b8ae0b3c379 differs
    from the published epic head fee2b7a57f1f85b44b82cc23b4e6734d27d5e4d1; refusing
    to reset a preserved recovery snapshot
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-06113f88fa72
    project_id: proj-14849f1b
    task_id: OOMPAH-790
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 953468f90e6665ecc591872730033212d35e1e12bbdc9280d4b0c8a26fc57807
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Direct-owner implementation was fully tested and published at exact head
      fee2b7a57 on epic-OOMPAH-767. Integration twice failed on server-side recovery
      state: first the parent epic branch was absent, then its preserved integration
      worktree remained at stale head a681ec2f despite the remote epic branch being
      fee2b7a57.'
    created_at: '2026-08-04T17:59:40.026402+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-790
    target_state: Done
    evidence_fingerprint: 953468f90e6665ecc591872730033212d35e1e12bbdc9280d4b0c8a26fc57807
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-04T17:59:47.950406+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Implement an in-memory reference machine from the workflow contract plus generators for tasks, statuses, dependency DAGs/cycles, nested epics, landing facts, audits, reviews, ownership generations, retries, and jobs. Generate valid and adversarial event sequences with deterministic seeds and shrinkable/replayable failure traces. Assert transition safety, unique ownership, evidence fencing, total disposition, and eventual progress when faults cease. Add dependency and runtime bounds suitable for CI. Acceptance: the harness explores compositions beyond example tests, emits minimal reproducible traces, and fails on seeded versions of known systemic bugs.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 17:56
---
Implemented deterministic bounded state-machine generation, stable JSON replay, 1-minimal trace shrinking, dependency/cycle and nested-epic compositions, ownership/job generation fencing, terminal evidence checks, eventual-progress reconciliation, and seeded faulty policies proving detection of stale callbacks, duplicate owners, lost retry wakeups, and unproven terminal transitions. Verification: 79 reference-harness tests and 277 composed workflow tests pass; Ruff, terminal mutation scan, and secret scan pass. Exact pushed head: fee2b7a57f1f85b44b82cc23b4e6734d27d5e4d1.
---
author: oompah
created: 2026-08-04 17:56
---
Added and verified deterministic generative workflow reference harness at fee2b7a57.
---
author: oompah
created: 2026-08-04 17:57
---
Integration could not verify `OOMPAH-790`: could not recover integration worktrees: git worktree add failed: fatal: invalid reference: origin/epic-OOMPAH-767

Fetch the private branch, preserve its commits, push a clean current head, and submit it again.
---
author: oompah
created: 2026-08-04 17:58
---
Resubmitted exact verified head fee2b7a57 after creating the previously absent parent epic branch epic-OOMPAH-767.
---
author: oompah
created: 2026-08-04 17:59
---
Integration could not verify `OOMPAH-790`: epic worktree head a681ec2fc005f339063b3b8e2a139b8ae0b3c379 differs from the published epic head fee2b7a57f1f85b44b82cc23b4e6734d27d5e4d1; refusing to reset a preserved recovery snapshot

Fetch the private branch, preserve its commits, push a clean current head, and submit it again.
---
author: oompah
created: 2026-08-04 17:59
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct-owner implementation was fully tested and published at exact head fee2b7a57 on epic-OOMPAH-767. Integration twice failed on server-side recovery state: first the parent epic branch was absent, then its preserved integration worktree remained at stale head a681ec2f despite the remote epic branch being fee2b7a57.
---
<!-- COMMENTS:END -->
