---
id: OOMPAH-577
type: task
status: In Progress
priority: null
title: Allow a changed integrated head to retry a failed completed terminal audit
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T03:07:59.102017Z'
updated_at: '2026-08-07T10:11:07.436257Z'
work_branch: OOMPAH-577
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/588
review_number: '588'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/588
oompah.review_number: '588'
oompah.work_branch: OOMPAH-577
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-98c92344aec1
    project_id: proj-14849f1b
    task_id: OOMPAH-577
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
    authorized_by:
      version: 1
      identity: lesserevil
      source: api
    reason: 'Restore proven merged state from PR #588 merge commit 70fa1de48 and recorded
      green CI/live evidence.'
    created_at: '2026-07-31T06:06:55.508737+00:00'
  applied_result_attempts:
    no-auditor-audit-c1eee8ef1fc2-2: '2026-08-07T07:22:36.552463+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-577
    target_state: Done
    evidence_fingerprint: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
    audit_ids:
    - audit-c1eee8ef1fc2
    kind: result
    applied: true
    retired_at: '2026-08-07T07:22:36.552473+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-577
    audit_id: audit-c1eee8ef1fc2
    attempt_id: no-auditor-audit-c1eee8ef1fc2-2
    target_state: Done
    evidence_fingerprint: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
    status: Needs Human
    audit_ids:
    - audit-c1eee8ef1fc2
    applied: true
    created_at: '2026-08-07T07:22:36.552485+00:00'
    applied_at: '2026-08-07T07:22:44.871987+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c1eee8ef1fc2
    project_id: proj-14849f1b
    task_id: OOMPAH-577
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
    attempts:
    - version: 1
      attempt_id: attempt-2d156054d52d
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
      created_at: '2026-07-31T06:06:20.213169+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T06:06:20.213169+00:00'
      branch_key: OOMPAH-577
      ended_at: '2026-08-07T07:09:55.501113+00:00'
      failure_reason: auditor session abandoned after attempt TTL
    - version: 1
      attempt_id: attempt-f6ea0cf6c239
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
      created_at: '2026-08-07T07:10:03.150107+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-07T07:10:03.150107+00:00'
      branch_key: OOMPAH-577
      candidate_rotation_count: 1
      failure_classification: infrastructure_error
      ended_at: '2026-08-07T07:10:29.385257+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-577 (tried: origin/OOMPAH-577)'
      next_retry_at: '2026-08-07T07:10:49.385204+00:00'
    - version: 1
      attempt_id: no-auditor-audit-c1eee8ef1fc2-2
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
      verdict: fail
      failure_classification: no_auditor
      created_at: '2026-08-07T07:22:36.552340+00:00'
      completed_at: '2026-08-07T07:22:36.552340+00:00'
    requested_by:
      version: 1
      identity: api-client
      source: api
    previous_state: In Review
    created_at: '2026-07-31T06:06:13.348111+00:00'
    updated_at: '2026-08-07T07:22:36.552340+00:00'
  - version: 1
    audit_id: audit-534d62772883
    project_id: proj-14849f1b
    task_id: OOMPAH-577
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
    attempts: []
    requested_by:
      version: 1
      identity: api-client
      source: api
    previous_state: In Review
    created_at: '2026-07-31T06:06:13.348111+00:00'
  - version: 1
    audit_id: audit-ddd74e1c9e1e
    project_id: proj-14849f1b
    task_id: OOMPAH-577
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 80e2c5927e01fa8dd501f592e9e8062ec6229b01926107d735232bfc4bf86daf
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-07T06:08:51.515138+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-2d156054d52d
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
    created_at: '2026-07-31T06:06:20.213169+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T06:06:20.213169+00:00'
    branch_key: OOMPAH-577
    ended_at: '2026-08-07T07:09:55.501113+00:00'
    failure_reason: auditor session abandoned after attempt TTL
  - version: 1
    attempt_id: attempt-f6ea0cf6c239
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 48fe0a0413a694bb96d0f317a7f6440aac564b1f9b3fac497a37a0bb5095d8cd
    created_at: '2026-08-07T07:10:03.150107+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-07T07:10:03.150107+00:00'
    branch_key: OOMPAH-577
    candidate_rotation_count: 1
    failure_classification: infrastructure_error
    ended_at: '2026-08-07T07:10:29.385257+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-577 (tried: origin/OOMPAH-577)'
    next_retry_at: '2026-08-07T07:10:49.385204+00:00'
oompah.task_costs:
  total_input_tokens: 564411
  total_output_tokens: 8745
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 22
      output_tokens: 549
      cost_usd: 0.0
    haiku:
      input_tokens: 376
      output_tokens: 2649
      cost_usd: 0.0
    sonnet:
      input_tokens: 564007
      output_tokens: 3782
      cost_usd: 0.0
    opus:
      input_tokens: 6
      output_tokens: 1765
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 22
    output_tokens: 549
    cost_usd: 0.0
    recorded_at: '2026-07-31T06:07:17.755570+00:00'
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2535
    cost_usd: 0.0
    recorded_at: '2026-08-07T08:44:29.586474+00:00'
  - profile: default
    model: haiku
    input_tokens: 366
    output_tokens: 114
    cost_usd: 0.0
    recorded_at: '2026-08-07T09:28:07.373181+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 27
    output_tokens: 208
    cost_usd: 0.0
    recorded_at: '2026-08-07T09:39:45.549668+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 563959
    output_tokens: 3427
    cost_usd: 0.0
    recorded_at: '2026-08-07T09:43:16.035210+00:00'
  - profile: deep
    model: opus
    input_tokens: 6
    output_tokens: 1765
    cost_usd: 0.0
    recorded_at: '2026-08-07T09:48:00.955492+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 21
    output_tokens: 147
    cost_usd: 0.0
    recorded_at: '2026-08-07T10:01:29.313044+00:00'
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 532ed209b86faa319390dd667bedd189ce6cd0e1911519f085b6328c0ca5bb4c
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T08:44:29.588247+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Scanned all 36 included candidates; no active non-terminal\
    \ task describes the same TerminalTransitionCoordinator changed-evidence-retry\
    \ behavior. All similar tasks (OOMPAH-217 through OOMPAH-227, covering handoff\
    \ workflows, safety limits, worktree reconciliation, and release delivery) are\
    \ archived/completed and address distinct problems. The referenced trigger OOMPAH-483\
    \ is not in the supplied corpus. OOMPAH-577's current Open status reflects stale\
    \ audit state, not duplication with another live task.\n# Duplicate Investigation:\
    \ OOMPAH-577\n\nI'll analyze OOMPAH-577 against the supplied project task corpus\
    \ to determine if it's a duplicate of any existing active task.\n\n## Analysis\n\
    \n**Current Task (OOMPAH-577):**\n- Status: Open\n- Title: \"Allow a changed integrated\
    \ head to retry a failed completed terminal audit\"\n- Description: Update TerminalTransitionCoordinator\
    \ so a completed audit record only rejects identical stale requests; when evidence\
    \ fingerprint changes after failed audit and new work, preserve old record as\
    \ Superseded and enqueue fresh Pending record\n- Key fact: Implementation merged\
    \ to main as commit 70fa1de48 (PR #588) on 2026-07-30; work is complete but task\
    \ status is stale\n\n**Corpus Review:**\nScanning all 36 included candidates in\
    \ the provided corpus:\n- All candidates except OOMPAH-577 itself are in terminal\
    \ states (Archived, Done, or Merged)\n- Closest related/similar tasks: OOMPAH-217\
    \ (handoff workflow), OOMPAH-218 (incomplete-session safety), OOMPAH-219 (shared-worktree\
    \ reconciliation), OOMPAH-210/211 (GitHub check-run access, comment delivery)\
    \ \u2014 all completed/archived\n- Referenced trigger OOMPAH-483 is not included\
    \ in the corpus\n- No structural required-peer matches (corpus metadata: `required_peer_count:\
    \ 0, omitted_required_peer_count: 0`)\n\n**Key Observation:**\nOOMPAH-577's unusual\
    \ status (Open after implementation merged) appears to be a stale-state issue,\
    \ not a duplicate. The task was implemented, merged, passed live verification,\
    \ then entered \"Needs Human\" during terminal audit (awaiting auditor), was reopened\
    \ by watchdog as actionable, and is now in duplicate screening \u2014 but this\
    \ represents a single task's lifecycle with lingering audit/state issues, not\
    \ a duplicate of another task.\n\n---\n\nFocus handoff: duplicate_detector\n\n\
    Duplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: Scanned\
    \ all 36 included candidates; no active non-terminal task describes the same TerminalTransitionCoordinator\
    \ changed-evidence-retry behavior. All similar t"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d356e0a9-c79d-4720-bd12-41e16369cbbe
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-577__20260807T083821Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-577
    source_sha: 39285e9c3db19ae0df1757ae3e49d74204ffca49
    completed_at: '2026-08-07T08:44:29.606369+00:00'
  - run_id: OOMPAH-577__20260807T094057Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: oompah_tests
    source_branch: OOMPAH-577
    source_sha: 39285e9c3db19ae0df1757ae3e49d74204ffca49
    completed_at: '2026-08-07T09:43:16.039518+00:00'
  - run_id: OOMPAH-577__20260807T094434Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: opus
    focus: oompah_tests
    source_branch: OOMPAH-577
    source_sha: 39285e9c3db19ae0df1757ae3e49d74204ffca49
    completed_at: '2026-08-07T09:48:00.958522+00:00'
---
## Summary

Triggered by: OOMPAH-483\n\nImplementation scope: update TerminalTransitionCoordinator request handling so a completed audit record only rejects an identical stale request. When the same target is requested with a different evidence fingerprint after a failed audit and new pushed/integrated work, preserve the old record as Superseded and enqueue a fresh Pending record. Do not allow duplicate same-fingerprint requests and do not weaken successful terminal-state idempotency. Ensure the integration completion sweep can move a Ready-to-Integrate task back to In Validation after its earlier audit failed and the integrated SHA changed. Relevant files: oompah/terminal_transition_coordinator.py, tests/test_terminal_transition_coordinator.py, and integration transition tests in tests/test_orchestrator_handlers.py. Tests: same-fingerprint completed rejection, changed-fingerprint completed supersession, preserved history/audit IDs, fresh pending record, and repeated sweep coalescing. Acceptance criteria: OOMPAH-483 at integrated SHA 11ea824f7 can enter a new independent Done audit instead of logging 'already completed'; identical completed evidence stays idempotently rejected; focused and full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 03:33
---
Implemented changed-completed-evidence retry at 7fc9aa8ae and merged PR #588 to main as 70fa1de48 after required Python 3.11/3.12/3.13 CI passed. Focused coordinator/integration tests: 115 passed. Complete Makefile gate: 13,617 passed, 7 skipped. Live verification: OOMPAH-483 superseded its earlier failed completed audit, entered a fresh audit at integrated SHA 11ea824f7, received an independent PASS after 209 focused auditor tests, and reached Done. Service restarted gracefully and is healthy.
---
author: oompah
created: 2026-07-31 06:06
---
Post-restart reconciliation: PR #588 merged this task to main as 70fa1de48 after all matrix checks and live verification. The current In Review display is stale; restoring Merged.
---
author: oompah
created: 2026-07-31 06:06
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 06:06
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 06:06
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 06:07
---
Override by lesserevil: terminal transition to Merged applied by project owner.

Reason: Restore proven merged state from PR #588 merge commit 70fa1de48 and recorded green CI/live evidence.
---
author: oompah
created: 2026-07-31 06:07
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 12, Tool calls: 10
- Tokens: 22 in / 549 out [571 total]
- Cost: $0.0000
- Exit: terminated, Duration: 56s
- Log: OOMPAH-577__20260731T060623Z.jsonl
---
author: oompah
created: 2026-08-07 07:10
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-07 07:10
---
Run #2 [attempt=2, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 9s
---
author: oompah
created: 2026-08-07 07:10
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-577 (tried: origin/OOMPAH-577). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-07 07:22
---
Needs Human — Done audit requires operator input.

No independent auditor candidate is available for this audit (All eligible auditor candidates were already attempted for this audit.). Configure the `auditor` role with at least one healthy provider/model that is independent of the task contributors, then have a project owner rearm this terminal audit. Please review the audit output, decide the next step, and update this task with your instructions.
---
author: oompah
created: 2026-08-07 07:28
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #12)

**State audited:** `Needs Human`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** current review 588 is merged
**Evidence result:** `merged`

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-08-07 08:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 08:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 08:44
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.5K out [2.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 38s
- Log: OOMPAH-577__20260807T083821Z.jsonl
---
author: oompah
created: 2026-08-07 08:46
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-07 08:46
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 08:55
---
**Understanding & Current Status:**

OOMPAH-577 implementation has been merged to main (commit 70fa1de48, PR #588). The work allows changed integrated heads to retry failed completed terminal audits.

**Key Implementation:**
- Modified TerminalTransitionCoordinator.request_transition to only reject completed requests with *identical* evidence fingerprints (stale)
- When the same target is requested with *changed* evidence fingerprint, the old completed record is marked SUPERSEDED and a fresh PENDING record is created
- Ensures independent audits can retry after earlier failure when integrated SHA changes
- Test added: changed_completed_evidence_queues_fresh_audit

**Current Status:**
- Work is merged and in HEAD
- Task status is stuck in 'In Progress' due to terminal audit process issues
- Stalled-task watchdog reopened as 'actionable'
- I'm verifying the implementation is correct by running focused tests

**Next Steps:** Run terminal_transition_coordinator focused tests to confirm all behavior works.
---
author: oompah
created: 2026-08-07 09:28
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 15
- Tokens: 366 in / 114 out [480 total]
- Cost: $0.0000
- Exit: terminated, Duration: 41m 23s
- Log: OOMPAH-577__20260807T084653Z.jsonl
---
author: oompah
created: 2026-08-07 09:29
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-07 09:29
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 09:39
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 11
- Tokens: 27 in / 208 out [235 total]
- Cost: $0.0000
- Exit: terminated, Duration: 10m 35s
- Log: OOMPAH-577__20260807T092927Z.jsonl
---
author: oompah
created: 2026-08-07 09:40
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-08-07 09:40
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 09:43
---
Agent completed successfully in 159s (567386 tokens)
---
author: oompah
created: 2026-08-07 09:43
---
Run #3 [attempt=3, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 11
- Tokens: 564.0K in / 3.4K out [567.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 39s
- Log: OOMPAH-577__20260807T094057Z.jsonl
---
author: oompah
created: 2026-08-07 09:43
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-577`. Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-08-07 09:44
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-07 09:44
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 09:48
---
Agent completed successfully in 218s (1771 tokens)
---
author: oompah
created: 2026-08-07 09:48
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/opus]
- Turns: 2, Tool calls: 0
- Tokens: 6 in / 1.8K out [1.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 38s
- Log: OOMPAH-577__20260807T094434Z.jsonl
---
author: oompah
created: 2026-08-07 09:48
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-577`. No stronger profile is configured; retrying with 'deep' in 20s (2/3).
---
author: oompah
created: 2026-08-07 09:49
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-08-07 09:49
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 10:01
---
Run #3 [attempt=3, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 10
- Tokens: 21 in / 147 out [168 total]
- Cost: $0.0000
- Exit: terminated, Duration: 12m 7s
- Log: OOMPAH-577__20260807T094942Z.jsonl
---
author: oompah
created: 2026-08-07 10:06
---
Retrying (attempt #3, agent: standard)
---
author: oompah
created: 2026-08-07 10:06
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 10:09
---
Understanding: A completed terminal audit must remain idempotent for identical target/evidence, but a failed audit with changed integrated evidence must be superseded and retried as a new Pending audit. I will inspect the coordinator and integration sweep, implement the smallest compatible change, and run the focused coordinator/orchestrator tests.
---
author: oompah
created: 2026-08-07 10:11
---
Discovery: Commit 70fa1de48 (PR #588) is already an ancestor of this worktree HEAD. Its coordinator logic rejects only completed records with matching target, fingerprint, and revision binding; changed evidence supersedes the historical record and stages a new Pending audit. The integrated completion path recomputes its fingerprint from the current integration record before requesting Done.
---
<!-- COMMENTS:END -->
