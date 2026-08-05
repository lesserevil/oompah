---
id: OOMPAH-815
type: task
status: In Progress
priority: null
title: Preserve accepted child branch identity across repair dispatch
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T00:29:12.870188Z'
updated_at: '2026-08-05T02:32:22.883677Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-815
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 16b4288530f95cbebd4c56f62ef0f26f61fc0cd1f8b5725bd524b9cadcbce151
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T00:34:07.324585+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: Closest active tasks are OOMPAH-811 (integration rebase/head-generation
    rearming) and OOMPAH-814 (test-fixture determinism). Neither covers the accepted
    child-branch identity split between submission, integration authority, and later
    repair workspace dispatch described here.

    Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none


    Evidence: Closest active tasks are OOMPAH-811 (integration rebase/head-generation
    rearming) and OOMPAH-814 (test-fixture determinism). Neither covers the accepted
    child-branch identity split between submission, integration authority, and later
    repair workspace dispatch described here.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d5851470-838f-4fe1-ad39-99a7a719d023
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-815
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-815
  base_branch: epic-OOMPAH-763
  base_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
  updated_at: '2026-08-05T00:35:24.666752+00:00'
oompah.task_costs:
  total_input_tokens: 48168
  total_output_tokens: 5288
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 48168
      output_tokens: 5288
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 48036
    output_tokens: 314
    cost_usd: 0.0
    recorded_at: '2026-08-05T00:34:07.322985+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 132
    output_tokens: 4974
    cost_usd: 0.0
    recorded_at: '2026-08-05T01:10:37.433216+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-815__20260805T003307Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-815
    source_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
    completed_at: '2026-08-05T00:34:07.357924+00:00'
---
## Summary

Live reproduction on OOMPAH-814 at 2026-08-05 00:26 UTC: a direct-owner implementation was validly submitted and recorded in oompah.integration with task_branch=OOMPAH-814 and exact head cb1446d4, while the issue work_branch remained null. After the exact full gate failed and the server dispatched a CI repair, workspace setup recomputed epic-OOMPAH-763--task-OOMPAH-814, found the registered OOMPAH-814 worktree on the accepted branch, refused to reset it, and failed before the worker started. The same split identity can affect any manually/directly submitted epic child and repeats on every repair. Implementation scope: define one canonical immutable accepted branch identity across owner claim, task submit validation, integration record, issue work_branch metadata, workspace registry, retry/recovery dispatch, and terminal audit. Either reject a noncanonical child branch before mutating tracker/queue, or safely persist and reuse a valid accepted branch; never recompute a different branch after acceptance. Preserve exact remote-head verification, parent-base containment, worktree no-reset safety, concurrent submission fencing, and existing hierarchical child branches. Required tests: exact OOMPAH-814 plain-branch submit then Needs CI Fix repair; restart before repair; null/stale work_branch; canonical hierarchical control; remote branch/head mismatch rejection; dirty/divergent registered worktree preservation; concurrent resubmit; OOMPAH-813-style branch; and no retry loop or duplicate worker. Acceptance: an accepted submission can always be repaired/audited on the same proven branch, invalid branches fail before queue/tracker mutation, and workspace setup never disagrees with persisted integration authority.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 00:32
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-08-05 00:32
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 00:34
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 0
- Tokens: 48.0K in / 314 out [48.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 24s
- Log: OOMPAH-815__20260805T003307Z.jsonl
---
author: oompah
created: 2026-08-05 00:35
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-05 00:35
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-05 00:36
---
Understanding: This task fixes a bug where accepted child branch identity is not preserved across repair dispatch. Root cause: when a direct-owner submits an epic child task on a plain branch (e.g., OOMPAH-814), the submission records task_branch=OOMPAH-814 in oompah.integration but leaves issue work_branch as null. On CI repair, workspace setup recomputes the canonical branch name (epic-OOMPAH-763--task-OOMPAH-814), which differs from the accepted branch (OOMPAH-814), causing a conflict with the registered worktree. Fix: persist the accepted branch identity at submission time and reuse it on repair/retry dispatch, never recomputing it. Starting with code exploration to find root cause.
---
author: oompah
created: 2026-08-05 00:45
---
Independent read-only audit found the exact contract: OOMPAH-576 safety guards work; its legacy expected_submission_branch fallback accepts identifier when work_branch is null. _persist_worker_submission then writes integration but never work_branch. Later _create_workspace_for_issue unconditionally derives the hierarchical child branch and overwrites accepted authority. Once IntegrationRecord has task_branch+head_sha, that pair must win and Issue.work_branch is only a projection; submission should atomically reconcile it, retry/workspace/audit must reuse it, and fresh unsubmitted dispatch may still derive hierarchy. Centralize the resolver across server normal/scoped/ACP submit, _create_workspace_for_issue, _retry_issue_branch, and audit branch key. OOMPAH-813 is the live regression shape (accepted OOMPAH-813 at eb5d with null work_branch); preserve OOMPAH-814's current hierarchical workaround. Add zero-mutation mismatch/concurrency/restart/no-reset regressions; do not weaken ProjectStore/integration-executor safety.
---
author: oompah
created: 2026-08-05 00:46
---
Containment detail: _git_submission_evidence uses merge-base only for changed paths and does not return base_sha; _submission_record only syntax-checks inherited/supplied base_sha and does not verify ancestry. If accepting/reusing a parented null-metadata branch, add server-authoritative read-only proof that origin/<submitted branch> exists at submitted head and the head is compatible with/descends from the expected recorded parent base before any tracker/queue write. Otherwise reject pre-mutation. The executor's later fetch/rebase guard is necessary but does not meet this task's pre-mutation acceptance.
---
author: oompah
created: 2026-08-05 01:07
---
Acceptance detail for same-head resubmission: _persist_worker_submission currently returns early when the integration record is unchanged and status is Ready. Reconcile/backfill Issue.work_branch from the accepted non-working IntegrationRecord before that early return, or include branch projection agreement in the idempotency condition. Otherwise legacy null/stale work_branch rows remain vulnerable after an idempotent resubmit. Add exact regression for same task_branch/head with null and conflicting stale work_branch, proving accepted integration authority wins and the projection is repaired atomically.
---
author: oompah
created: 2026-08-05 01:10
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 92
- Tokens: 132 in / 5.0K out [5.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 35m 21s
- Log: OOMPAH-815__20260805T003530Z.jsonl
---
author: oompah
created: 2026-08-05 02:32
---
Review found a remaining Ready-to-Integrate set-status/status-label bypass around the unified submit transaction. Forward repair is pushed at 3b96e04bb03da5da724199945997c5ba15c831b7: task-scoped ACP/API and scoped HTTP now reject Ready aliases and label equivalents with the must-use-submit diagnostic before mutation. 34 focused tests pass; awaiting independent re-review.
---
<!-- COMMENTS:END -->
