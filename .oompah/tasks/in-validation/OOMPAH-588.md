---
id: OOMPAH-588
type: epic
status: In Validation
priority: 1
title: Finish safe repository hygiene and maintenance correctness
parent: OOMPAH-584
children:
- OOMPAH-600
- OOMPAH-601
- OOMPAH-602
- OOMPAH-603
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:13:46.482910Z'
updated_at: '2026-07-31T05:03:19.643666Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-324180823f32
    project_id: proj-14849f1b
    task_id: OOMPAH-588
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cff28373e3c1ee4569653cad01553f25c79d3bef7dd3dd6f38b99c5b27c00ae1
    attempts:
    - version: 1
      attempt_id: attempt-d986f94b1463
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: cff28373e3c1ee4569653cad01553f25c79d3bef7dd3dd6f38b99c5b27c00ae1
      created_at: '2026-07-31T05:03:04.101670+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T05:03:04.101670+00:00'
      branch_key: OOMPAH-588
    requested_by:
      version: 1
      identity: orchestrator
    previous_state: Open
    created_at: '2026-07-31T05:02:58.950383+00:00'
    updated_at: '2026-07-31T05:03:04.101670+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-d986f94b1463
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cff28373e3c1ee4569653cad01553f25c79d3bef7dd3dd6f38b99c5b27c00ae1
    created_at: '2026-07-31T05:03:04.101670+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T05:03:04.101670+00:00'
    branch_key: OOMPAH-588
---
## Summary

Goal

Finish aggressive but safe worktree/branch pruning and remove maintenance errors/noise that obscure real faults. Reuse OOMPAH-581, preserve dirty or unmerged work, repair project-scoped merged-label maintenance, and make cleanup outcomes measurable.

Relevant context

The managed oompah repository retained 20 registered worktrees, 117 local branches, and 67 remote branches. Cleanup itself reported no fatal error, but emitted repeated terminal-branch ownership warnings and a slow tick; merged_labels rejected OOMPAH-476 for missing project_id. OOMPAH-581 is already implemented and Ready to Integrate.

Acceptance criteria

Safe terminal artifacts are pruned on schedule; dirty/unmerged/shared-owner work is preserved; ownership skips are aggregated instead of warning-flooded; cleanup latency and categorized skip counts are visible; merged-label maintenance always resolves project scope without unsafe legacy fallback; focused and complete gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 14:20
---
Children are accepted and open; activate the hygiene recovery epic.
---
author: oompah
created: 2026-07-31 01:00
---
Operator recovery for the live nested-epic queue deadlock: rebased origin/epic-OOMPAH-588 from 89dfc1881 onto current parent origin/epic-OOMPAH-584 d62dd4cff and force-pushed with an exact lease at b4959703e. The three OOMPAH-602 commits replayed cleanly; adjusted one maintenance-scope test mock for the newer authoritative landing-ref refresh. Focused merged-label scope and rollup verification: 33 passed; terminal mutation scan passed.
---
author: oompah
created: 2026-07-31 05:03
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 05:03
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 05:03
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
