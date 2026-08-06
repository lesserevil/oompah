---
id: OOMPAH-840
type: task
status: In Validation
priority: null
title: Recover ready children whose terminal parent branch was pruned
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T18:21:39.670324Z'
updated_at: '2026-08-06T01:47:55.285837Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-840
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 52f697a2b11d797e87a4f0c4c40cf990f477ff479a52931be50caab547e7f51d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T00:03:09.728117+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The task corpus includes all 22 required structural peers\
    \ (OOMPAH-763 epic parent, OOMPAH-764\u2013771 workflow-engine infrastructure,\
    \ OOMPAH-806\u2013822 domain-specific fixes). None describe child recovery of\
    \ pruned terminal parents. Related but distinct active tasks cover prerequisite\
    \ reachability (OOMPAH-808), capacity reservation (OOMPAH-809), integration rearm\
    \ (OOMPAH-811), and branch identity (OOMPAH-815), but no task combines the exact\
    \ recovery requirement: detecting that a child's exact head is already landed\
    \ in the parent's target, bypassing integration, and staging terminal transition\
    \ without branch recreation.\nLooking at OOMPAH-840 in the context of the supplied\
    \ project task corpus, I need to compare it against active (non-terminal) peer\
    \ tasks to determine whether this is a duplicate of an existing issue.\n\n**OOMPAH-840\
    \ Core Problem:**\n- Ready/blocked children whose terminal parent epic is Merged/Archived\
    \ and has been pruned from remote\n- Example: OOMPAH-523 re-submitted at head\
    \ 9ea2b5523, but parent epic OOMPAH-521 is Merged and remote epic-OOMPAH-521 was\
    \ correctly pruned\n- The exact child head is reachable from origin/main, so it\
    \ should NOT require recreation of the deleted branch\n- Needs recovery path through\
    \ authoritative parent target/merge metadata without consuming retry_forced authority\
    \ wastefully\n\n**Comparison Against Active Peers:**\n\n1. **OOMPAH-768 (In Progress)**:\
    \ \"Migrate every workflow domain to shared decisions and durable jobs\" \u2014\
    \ A large epic covering integration queue, terminal-audit, review, implementation\
    \ domains. While OOMPAH-840 may be *part* of the migration scope, OOMPAH-768 is\
    \ about the broad infrastructure cutover, not the specific child-recovery defect.\n\
    \n2. **OOMPAH-769-771, OOMPAH-770**: Infrastructure epics for transition service,\
    \ liveness, and reconciler retirement \u2014 None address the specific pruned-parent\
    \ child recovery issue.\n\n3. **OOMPAH-807 (Done)**: \"Allow revisionless audits\
    \ for metadata-only Archived dispositions\" \u2014 About separating code-bearing\
    \ from metadata-only audits, not about recovering children whose heads are already\
    \ landed.\n\n4. **OOMPAH-808 (Open)**: \"Fence nested-epic dispatch until prerequisite\
    \ code is reachable\" \u2014 About proving hard-start prerequisite code is reachable\
    \ before nested worker launch. This is a different problem (prerequisite validation)\
    \ not child recovery of pruned terminals.\n\n5. **OOMPAH-809, OOMPAH-810, OOMPAH-811,\
    \ OOMPAH-815, OOMPAH-816-817, OOMPAH-822, OOMPAH-831**: These address capacity\
    \ management, auditor delivery, integration rearm, branch identity preservation,\
    \ validation serialization, recovery persist"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-840
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-763--task-OOMPAH-840
  base_branch: epic-OOMPAH-763
  base_sha: 58ffd477b19f370c7ed53a191e1a05580b016c85
  head_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
  integrated_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
  submitted_at: '2026-08-06T00:40:51.324740+00:00'
  updated_at: '2026-08-06T01:40:07.154768+00:00'
oompah.task_costs:
  total_input_tokens: 16
  total_output_tokens: 5124
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 3035
      cost_usd: 0.0
    unknown:
      input_tokens: 6
      output_tokens: 2089
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 3035
    cost_usd: 0.0
    recorded_at: '2026-08-06T00:03:09.721036+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 2089
    cost_usd: 0.0
    recorded_at: '2026-08-06T01:47:30.603828+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-840__20260806T000048Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-840
    source_sha: 58ffd477b19f370c7ed53a191e1a05580b016c85
    completed_at: '2026-08-06T00:03:09.749857+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-bf47fb6355f1
    project_id: proj-14849f1b
    task_id: OOMPAH-840
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 056220802f523a752467dfd9e9312bd9efa49cb5b0a7109e5a755ecdfac40e95
    attempts:
    - version: 1
      attempt_id: attempt-0d709983b605
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 056220802f523a752467dfd9e9312bd9efa49cb5b0a7109e5a755ecdfac40e95
      created_at: '2026-08-06T01:42:33.425979+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-06T01:42:33.425979+00:00'
      branch_key: epic-OOMPAH-763--task-OOMPAH-840
      failure_classification: finalization_failure
      ended_at: '2026-08-06T01:47:32.507772+00:00'
      failure_reason: normal
      next_retry_at: '2026-08-06T01:47:42.507746+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-06T01:40:25.353836+00:00'
    updated_at: '2026-08-06T01:47:32.507772+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-0d709983b605
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 056220802f523a752467dfd9e9312bd9efa49cb5b0a7109e5a755ecdfac40e95
    created_at: '2026-08-06T01:42:33.425979+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-06T01:42:33.425979+00:00'
    branch_key: epic-OOMPAH-763--task-OOMPAH-840
    failure_classification: finalization_failure
    ended_at: '2026-08-06T01:47:32.507772+00:00'
    failure_reason: normal
    next_retry_at: '2026-08-06T01:47:42.507746+00:00'
---
## Summary

Live reproduction: OOMPAH-523 was re-submitted at unchanged verified head 9ea2b5523 after OOMPAH-838 deployed. IntegrationQueueStore atomically consumed the one-shot retry_forced flag, then the integration executor blocked before the gate because parent epic OOMPAH-521 is already Merged and remote epic-OOMPAH-521 was correctly pruned. The exact task head is reachable from origin/main, so asking an operator to recreate or resubmit a deleted terminal container is wrong and consumes explicit retry authority without progress. OOMPAH-526 is another Ready child of the same terminal parent.\n\nImplementation scope:\n- Before requiring a live epic target branch, reconcile a Ready/blocked child whose parent/container is Merged or Archived using authoritative parent target/merge metadata, the task work branch/head, durable integration history, terminal audit evidence, and Git ancestry.\n- If the exact child head is already reachable from the parent landed target (for example origin/main), bypass integration and durably stage the correct terminal child transition through TaskTransitionService/terminal-audit workflow. Never recreate a pruned terminal epic branch.\n- If the head is not landed but recoverable, create/route an explicit recovery container or target rather than repeatedly blocking against the deleted branch. Fail closed with one actionable reason when evidence is ambiguous or unreachable.\n- Do not consume one-shot retry_forced authority until all non-gate preconditions that can be validated first (including target selection/existence) are satisfied, or persist a retry receipt that can be safely restored when no gate attempt occurred.\n- Coordinate with OOMPAH-696/699 landing-evidence reconciliation and OOMPAH-836 durable integration actions; no legacy direct status writer.\n\nRequired tests:\n- Merged parent with pruned epic branch + Ready child exact head reachable from origin/main converges to audited terminal state without gate/recreated branch.\n- Same with a blocked integration row after claim/preflight restarts idempotently and retires the warning.\n- One-shot retry authority is not lost when target preflight fails before a gate runs.\n- A truly unlanded child gets a named recovery target or one fail-closed action, not a resubmit loop.\n- Archived parent, unreachable Git evidence, multi-project identical identifiers, and OOMPAH-523/OOMPAH-526 sibling ordering are covered.\n\nAcceptance criteria: a late/reopened child of a terminal pruned epic either converges from exact landing proof or receives one explicit recovery path; it never blocks forever on a branch that lifecycle cleanup intentionally deleted, and forced-gate retry authority is consumed exactly once only by an actual gate attempt.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 18:27
---
Second live reproduction after project resume: OOMPAH-505 completed its deployment/configuration verification, submitted exact pushed head e1b0f4846, then blocked on the intentionally pruned remote epic-OOMPAH-502 even though that exact head is reachable from origin/main and parent OOMPAH-502 is Merged. This confirms the defect is generic to late/reopened children of terminal epics, not specific to authentication epic OOMPAH-521.
---
author: oompah
created: 2026-08-06 00:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 00:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 00:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 3.0K out [3.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 1s
- Log: OOMPAH-840__20260806T000048Z.jsonl
---
author: oompah
created: 2026-08-06 00:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 00:04
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 00:05
---
Understanding: I will trace integration preflight and terminal-audit handling for Ready children of Merged/Archived parents, identify why pruned parent branches block exact landed heads, then implement focused reconciliation and retry-authority preservation with regression tests.
---
author: oompah
created: 2026-08-06 00:06
---
Discovery: Existing OOMPAH-696 reconciliation handles Done children, but Ready-to-Integrate resubmissions still enter the per-epic queue and _execute_integration_item unconditionally requires the parent epic branch. A pruned terminal parent therefore returns missing_epic before any useful reconciliation. I am mapping durable evidence and transition APIs for a preflight recovery lane.
---
author: oompah
created: 2026-08-06 00:38
---
Verification: focused queue tests pass (26); terminal-parent regressions pass for Merged/Archived parents, exact landing, blocked restart, audit-evidence fallback, unlanded recovery, and retry receipt (5 new cases); full affected epic/integration suites pass (265 tests); neighboring integration/worker (33), parallel-epic (198), and terminal-audit/transition checks pass (198 selected); terminal mutation scan passes.
---
author: oompah
created: 2026-08-06 00:40
---
Implementation: Added pre-claim terminal-parent reconciliation for Ready/blocked queue rows, durable preflight blocking that preserves retry_forced, exact Git/audit landing proof, audited Merged staging with integrated metadata, and stable named recovery routing for ambiguous/unlanded heads. Added regression coverage for merged/archived parents, pruned branches, restart/idempotency, retry receipts, audit fallback, and recovery comments.
---
author: oompah
created: 2026-08-06 00:40
---
Completion: Commit 93cc4c856 is pushed on epic-OOMPAH-763--task-OOMPAH-840; the worktree is clean and up to date with origin. The implementation is ready for integration.
---
author: oompah
created: 2026-08-06 00:41
---
Recover Ready/blocked children of pruned terminal parents using exact landing/audit evidence, preserve preflight retry authority, and route ambiguous work to named recovery targets with regression coverage.
---
author: oompah
created: 2026-08-06 00:41
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 182
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 37m 9s
- Log: OOMPAH-840__20260806T000439Z.jsonl
---
author: oompah
created: 2026-08-06 01:40
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-06 01:42
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-06 01:42
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-06 01:47
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 2, Tool calls: 0
- Tokens: 6 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 51s
- Log: OOMPAH-840__20260806T014259Z.jsonl
---
author: oompah
created: 2026-08-06 01:47
---
Auditor attempt ended: auditor exited (normal) without a result. A different independent auditor will be tried on the next scheduler tick.
---
<!-- COMMENTS:END -->
