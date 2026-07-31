---
id: OOMPAH-460
type: epic
status: In Validation
priority: 1
title: Expose terminal audits in the UI, observability, migration, and end-to-end
  tests
parent: null
children:
- OOMPAH-484
- OOMPAH-485
- OOMPAH-486
- OOMPAH-487
- OOMPAH-488
- OOMPAH-489
- OOMPAH-580
- OOMPAH-583
- OOMPAH-606
- OOMPAH-609
- OOMPAH-611
- OOMPAH-613
- OOMPAH-614
- OOMPAH-634
- OOMPAH-635
- OOMPAH-636
- OOMPAH-638
- OOMPAH-639
blocked_by:
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:03:47.776498Z'
updated_at: '2026-07-31T06:16:40.414885Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-053f80903b1e: '2026-07-31T04:36:09.005592+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-072565b727d5
    project_id: proj-14849f1b
    task_id: OOMPAH-460
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fd0747b9bdba754f77a8fc86c71d70ecdff91f8b3cbad76a463dd53d3644e757
    attempts:
    - version: 1
      attempt_id: attempt-053f80903b1e
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: fd0747b9bdba754f77a8fc86c71d70ecdff91f8b3cbad76a463dd53d3644e757
      created_at: '2026-07-31T04:24:57.796303+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T04:24:57.796303+00:00'
      branch_key: OOMPAH-460
      verdict: pass
      completed_at: '2026-07-31T04:36:09.005406+00:00'
      ended_at: '2026-07-31T04:36:09.005406+00:00'
    requested_by:
      version: 1
      identity: orchestrator
    previous_state: Open
    created_at: '2026-07-31T04:24:53.487735+00:00'
    updated_at: '2026-07-31T04:36:09.005406+00:00'
  - version: 1
    audit_id: audit-2b50ca0977be
    project_id: proj-14849f1b
    task_id: OOMPAH-460
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fd0747b9bdba754f77a8fc86c71d70ecdff91f8b3cbad76a463dd53d3644e757
    attempts:
    - version: 1
      attempt_id: attempt-01ce9e329c32
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: fd0747b9bdba754f77a8fc86c71d70ecdff91f8b3cbad76a463dd53d3644e757
      created_at: '2026-07-31T06:16:38.724130+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T06:16:38.724130+00:00'
      branch_key: OOMPAH-460
    requested_by:
      version: 1
      identity: api-client
      source: api
    previous_state: Done
    created_at: '2026-07-31T06:16:27.453081+00:00'
    updated_at: '2026-07-31T06:16:38.724130+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-053f80903b1e
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fd0747b9bdba754f77a8fc86c71d70ecdff91f8b3cbad76a463dd53d3644e757
    created_at: '2026-07-31T04:24:57.796303+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T04:24:57.796303+00:00'
    branch_key: OOMPAH-460
  - version: 1
    attempt_id: attempt-01ce9e329c32
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fd0747b9bdba754f77a8fc86c71d70ecdff91f8b3cbad76a463dd53d3644e757
    created_at: '2026-07-31T06:16:38.724130+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T06:16:38.724130+00:00'
    branch_key: OOMPAH-460
oompah.task_costs:
  total_input_tokens: 185
  total_output_tokens: 7463
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 185
      output_tokens: 7463
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 185
    output_tokens: 7463
    cost_usd: 0.0
    recorded_at: '2026-07-31T04:36:26.861632+00:00'
---
## Summary

Goal

Make independent terminal auditing understandable and operable: expose In Validation and audit progress in APIs and the dashboard, provide actionable health signals, document configuration and owner overrides, migrate existing installations safely, and validate the complete lifecycle end to end.

Required behavior

- The board and task detail surfaces show In Validation, requested target, audit phase, attempts, evidence revision, safe auditor identity, and latest verdict.
- Service status reports queued/running/passed/failed/retried/stale/overridden/no-candidate metrics.
- Alerts appear only for actionable audit stalls or missing independent candidates; normal successful audits are not alerts.
- Existing terminal records are grandfathered once and remain stable across restart. A later status or evidence change invalidates the grandfather record.
- Old OOMPAH_VERIFY_COMPLETION settings are deprecated with clear startup and operator guidance.
- End-to-end tests cover worker to Done audit, review merge to Merged audit, archive audit, nested/shared epics, stale verdicts, restart recovery, and owner override.

Constraints

Build after terminal paths are integrated. Configuration examples go in .env.example and user-facing operation guidance goes in docs/. Documentation diagrams must use Mermaid. All code changes require tests.

Acceptance criteria

Operators can see why a task is waiting, which evidence was audited, what action is required on failure, and whether the system has an eligible independent auditor. Upgrade and complete lifecycle tests pass through make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:10
---
Queued for execution. Every child explicitly depends on OOMPAH-459, so no epic-OOMPAH-460 branch/worktree will be created until OOMPAH-459 has landed. Its first dispatch will therefore branch from the then-latest main.
---
author: oompah
created: 2026-07-31 04:24
---
Recovery reconciliation: origin/main is an ancestor of current origin/epic-OOMPAH-460 (0 behind, 6 ahead at 0d7c3578f); OOMPAH-634 is Done and duplicate OOMPAH-636 Archived. Cleared stale rebase-requested/epic:rebasing labels so normal epic rollup and PR maintenance can resume.
---
author: oompah
created: 2026-07-31 04:24
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 04:24
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 04:25
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 04:36
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- children_done_count: 13
- children_archived_count: 5
- rollup_derivation: epic_rollup_state({Done, Archived}) = Done
- epic_branch_head: origin/epic-OOMPAH-460 @ 0d7c3578f (6 ahead of origin/main 24bd5d6c1)
- epic_branch_commits: abe100801 (486 observability), ce71b2409 (486 lifecycle gaps), df440b431 (486 recovery alerts), fd19b48db (486 throughput stat), 172198528 (489 lifecycle contract), 0d7c3578f (489 contract fixes)
- override_reference_head: 44e5c5579 via 5d88239c9 on origin/epic-OOMPAH-587 (OOMPAH-597 recovery chain)
- override_authorizer: lesserevil (project owner)
- blocked_by_status: OOMPAH-459 integrated on origin/main at 6be5c8910
- evidence_fingerprint_match: state branch pending_chain digest fd0747b9bdba754f77a8fc86c71d70ecdff91f8b3cbad76a463dd53d3644e757 matches trusted scheduler input
---
author: oompah
created: 2026-07-31 04:36
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 141
- Tokens: 185 in / 7.5K out [7.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 11m 28s
- Log: OOMPAH-460__20260731T042504Z.jsonl
---
author: oompah
created: 2026-07-31 06:16
---
Post-recovery closure: all implementation children are Done or Archived, their reviewed feature commits are present in merged main via recovery PR #603, the exact main gate passed (14,163 passed), terminal audit passed, and GitHub CI was green. Archiving the superseded epic branch prevents duplicate review/delivery while retaining the audit record.
---
<!-- COMMENTS:END -->
