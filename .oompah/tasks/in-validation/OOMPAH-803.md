---
id: OOMPAH-803
type: task
status: In Validation
priority: 1
title: Route API and auxiliary status writes through TaskTransitionService
parent: OOMPAH-769
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T14:01:03.399587Z'
updated_at: '2026-08-04T21:23:35.955905Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-82e9f76863be
    project_id: proj-14849f1b
    task_id: OOMPAH-803
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: eb494fb935fa376f8b9ef3849f383fa4b43dcddb370660c2f1dac3efd75d5585
    attempts:
    - version: 1
      attempt_id: attempt-869dd7e8a2d7
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: eb494fb935fa376f8b9ef3849f383fa4b43dcddb370660c2f1dac3efd75d5585
      created_at: '2026-08-04T21:23:15.732289+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:23:15.732289+00:00'
      branch_key: OOMPAH-803
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T21:23:27.174812+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-803 (tried: origin/OOMPAH-803)'
      next_retry_at: '2026-08-04T21:23:37.174783+00:00'
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Backlog
    created_at: '2026-08-04T21:22:32.673831+00:00'
    updated_at: '2026-08-04T21:23:27.174812+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-869dd7e8a2d7
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: eb494fb935fa376f8b9ef3849f383fa4b43dcddb370660c2f1dac3efd75d5585
    created_at: '2026-08-04T21:23:15.732289+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:23:15.732289+00:00'
    branch_key: OOMPAH-803
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T21:23:27.174812+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-803 (tried: origin/OOMPAH-803)'
    next_retry_at: '2026-08-04T21:23:37.174783+00:00'
---
## Summary

Migrate server/API/CLI handoff, stalled watchdog, audit enforcement, ACP tools, intake, projects, and auxiliary writers. Preserve authenticated-principal/owner rules and compatibility. Add AST boundary enforcement prohibiting direct production status writes outside service/adapters. Test REST/CLI, owner claims, intake, Needs Human, terminal aliases, and violations. Acceptance: every production transition is service-owned, journaled, and reason-coded.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:22
---
Archiving as an exact duplicate of the earlier, more actionable OOMPAH-775. Both cover the same API/CLI/watchdog/audit/auxiliary TaskTransitionService migration and AST enforcement boundary; keeping both nonterminal would duplicate implementation and prevent OOMPAH-769 rollup.
---
author: oompah
created: 2026-08-04 21:22
---
Queued for terminal transition to Archived. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-04 21:23
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 21:23
---
Run #1 [attempt=1, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 5s
---
author: oompah
created: 2026-08-04 21:23
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-803 (tried: origin/OOMPAH-803). A different independent auditor will be tried on the next scheduler tick.
---
<!-- COMMENTS:END -->
