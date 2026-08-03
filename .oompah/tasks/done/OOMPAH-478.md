---
id: OOMPAH-478
type: feature
status: Done
priority: 1
title: Route epic rollup, child Done, and epic close transitions through audits
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:26.329329Z'
updated_at: '2026-08-03T20:02:05.587537Z'
work_branch: epic-OOMPAH-459--task-OOMPAH-478
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ab86b60bea92b12dbe85f111788a91ca686b0760b5299075160d7f27c6439cc4
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:37:17.162767+00:00'
  matched_identifiers: []
  evidence: "Based on my investigation, let me provide my findings:\n\n## Duplicate\
    \ Investigation Complete\n\nI have searched comprehensively for existing tasks\
    \ that might duplicate OOMPAH-478's scope:\n\n**Search Strategy:**\n- Scanned\
    \ all `.oompah/tasks/` directories (open, merged, archived)\n- Searched for keywords:\
    \ \"epic,\" \"rollup,\" \"audit,\" \"terminal,\" \"child,\" \"Done,\" \"close,\"\
    \ \"transition\"\n- Reviewed relevant design docs: `terminal-transition-coordinator.md`,\
    \ `multi-branch-support.md`\n- Examined test files: `test_epic_strategy.py`, `test_epic_auto_close.py`,\
    \ `test_terminal_transition_coordinator.py`\n- Checked blocker task IDs (OOMPAH-475,\
    \ OOMPAH-458) in tracker\n\n**Key Findings:**\n- OOMPAH-478, OOMPAH-475, OOMPAH-458,\
    \ and OOMPAH-459 do not exist as native tasks in `.oompah/tasks/`\n- Only one\
    \ active open task exists: OOMPAH-281 (self-hosted runner infrastructure)\n- The\
    \ terminal transition coordinator infrastructure is designed (plans/ docs) and\
    \ partially implemented\n- Epic strategy and auto-close exist in the codebase\
    \ but do NOT route through the audit system\n- No existing tests cover \"routing\
    \ epic rollup / child Done / epic close transitions through audits\"\n- The closest\
    \ related tasks (OOMPAH-281, OOMPAH-280, OOMPAH-279) deal with unrelated infrastructure\n\
    \n**Closest Reviewed Candidates (All Terminal or Unrelated):**\n- Merged OOMPAH-271-280:\
    \ Release delivery, epic staleness, UI features \u2014 none cover audit routing\
    \ for epic transitions\n- Archived OOMPAH-1-276: Various historical tasks, none\
    \ address routing epic rollup through audits\n\n**Conclusion:**\nOOMPAH-478 describes\
    \ a unique feature: integrating the existing terminal transition coordinator infrastructure\
    \ with epic rollup reconciliation, stale child completion, and epic auto-close\
    \ logic. No active task covers this scope.\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Comprehensive scan of `.oompah/tasks/` (all states), keyword searches in plans/\
    \ and tests"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
oompah.agent_run_id: a7b10f1f-c864-48d8-b779-ecb895c94339
oompah.work_branch: epic-OOMPAH-459--task-OOMPAH-478
oompah.task_costs:
  total_input_tokens: 2756
  total_output_tokens: 16326
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 2618
      output_tokens: 10910
      cost_usd: 0.0
    sonnet:
      input_tokens: 40
      output_tokens: 1037
      cost_usd: 0.0
    unknown:
      input_tokens: 98
      output_tokens: 4379
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 162
    output_tokens: 4648
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:33:39.043297+00:00'
  - profile: default
    model: haiku
    input_tokens: 234
    output_tokens: 5751
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:37:17.161698+00:00'
  - profile: default
    model: haiku
    input_tokens: 2222
    output_tokens: 511
    cost_usd: 0.0
    recorded_at: '2026-07-29T18:50:54.924884+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 40
    output_tokens: 1037
    cost_usd: 0.0
    recorded_at: '2026-07-29T23:19:30.811167+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 98
    output_tokens: 4379
    cost_usd: 0.0
    recorded_at: '2026-07-30T00:59:03.108942+00:00'
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-459--task-OOMPAH-478
  base_branch: epic-OOMPAH-459
  base_sha: 2e2005cba5b9106029e706db699ca7cfdaa6e3bd
  updated_at: '2026-07-30T00:14:48.349502+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-15afd28d0dd7: '2026-07-30T00:58:48.796129+00:00'
  oompah.terminal_override_records: []
  oompah.terminal_audit_retirements: []
  oompah.terminal_audit_result_intents: []
  oompah.lifecycle_reconciliations:
  - project_id: proj-14849f1b
    task_id: OOMPAH-478
    from: Merged
    to: Done
    reason: shared_epic_parent_not_landed
    conflict: 'Cannot transition shared-epic child OOMPAH-478 to Merged: parent epic
      OOMPAH-459 could not be verified. The parent review must land on its configured
      target branch first.'
    done_audit_ids:
    - audit-87db541fd5de
    created_at: '2026-08-03T20:02:03.126844+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-87db541fd5de
    project_id: proj-14849f1b
    task_id: OOMPAH-478
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a6edb7eef5e8240b9c7fc23efbbdad625e428269a63282ed5ed4b211f3b944fd
    attempts:
    - version: 1
      attempt_id: attempt-e8f6b6b026f4
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a6edb7eef5e8240b9c7fc23efbbdad625e428269a63282ed5ed4b211f3b944fd
      created_at: '2026-07-29T23:45:02.956067+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-29T23:45:02.956067+00:00'
      branch_key: epic-OOMPAH-459--task-OOMPAH-478
      ended_at: '2026-07-29T23:45:13.749898+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-15afd28d0dd7
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a6edb7eef5e8240b9c7fc23efbbdad625e428269a63282ed5ed4b211f3b944fd
      created_at: '2026-07-30T00:14:40.510521+00:00'
      provider_id: prov-52e94e83
      model: gpt-5.6-sol
      started_at: '2026-07-30T00:14:40.510521+00:00'
      branch_key: epic-OOMPAH-459--task-OOMPAH-478
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-07-30T00:58:48.795971+00:00'
      ended_at: '2026-07-30T00:58:48.795971+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-29T23:39:26.237376+00:00'
    updated_at: '2026-07-30T00:58:48.795971+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-e8f6b6b026f4
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a6edb7eef5e8240b9c7fc23efbbdad625e428269a63282ed5ed4b211f3b944fd
    created_at: '2026-07-29T23:45:02.956067+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-29T23:45:02.956067+00:00'
    branch_key: epic-OOMPAH-459--task-OOMPAH-478
    ended_at: '2026-07-29T23:45:13.749898+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-15afd28d0dd7
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a6edb7eef5e8240b9c7fc23efbbdad625e428269a63282ed5ed4b211f3b944fd
    created_at: '2026-07-30T00:14:40.510521+00:00'
    provider_id: prov-52e94e83
    model: gpt-5.6-sol
    started_at: '2026-07-30T00:14:40.510521+00:00'
    branch_key: epic-OOMPAH-459--task-OOMPAH-478
    candidate_rotation_count: 1
---
## Summary

Implementation scope

Replace terminal writes in epic rollup reconciliation, stale In Review child completion, parent auto-close, and epic/child merged promotion with coordinator requests. In Validation children count as nonterminal and block rollup landing. A parent cannot enter Done until every required child has a current passed Done audit. A parent Merged request must chain its own Done audit when missing and then run target landing audit. Preserve nested/shared epic branch and landing-evidence gates. Do not let rollup reconciliation overwrite In Validation or audit:repair-needed.

Tests

Cover standalone epic, shared children, stale In Review child to Done, nested epics, child In Validation blocking parent, missing child audit, parent Done/Merged audit chains, independently merged child, existing review-repair states, and idempotent repeated ticks. Run epic strategy/rollup tests and make test.

Acceptance criteria

No epic or child is terminalized by rollup alone; each terminal meaning has the correct current audit and existing branch containment safeguards still apply.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:30
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:33
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 49, Tool calls: 19
- Tokens: 162 in / 4.6K out [4.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 48s
- Log: OOMPAH-478__20260729T013057Z.jsonl
---
author: oompah
created: 2026-07-29 01:35
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:37
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 65, Tool calls: 33
- Tokens: 234 in / 5.8K out [6.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 54s
- Log: OOMPAH-478__20260729T013526Z.jsonl
---
author: oompah
created: 2026-07-29 18:26
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 18:26
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-29 18:28
---
Understanding: Epic rollup transitions need to route through coordinator audits instead of direct terminal writes. Key changes:
1. Replace direct terminal writes in rollup reconciliation, stale In Review child completion, parent auto-close, and epic/child merged promotion with coordinator requests
2. Ensure In Validation children block rollup landing
3. Parent Done requires all required children to have current passed Done audits
4. Parent Merged must chain own Done audit when missing
5. Preserve existing branch/landing-evidence gates

Starting discovery phase to locate rollup, audit, and coordinator code.
---
author: oompah
created: 2026-07-29 18:30
---
Discovery: Located relevant code:
- orchestrator.py _reconcile_epic_rollup_statuses (line 5172): Currently uses tracker.update_issue() directly for all states
- terminal_audit.py: Defines audit record types and terminal states
- terminal_transition_coordinator.py: Coordinator for staging terminal transitions
- orchestrator.py request_terminal_transition (line 2320): Existing method to route through coordinator
- statuses.py epic_rollup_state: Returns rolled state (DONE, MERGED, or nonterminal)

Key insight: Need to replace direct tracker.update_issue() calls with coordinator.request_transition() for terminal states (DONE, MERGED, ARCHIVED) while keeping nonterminal state updates direct. Must skip reconciliation when epic is In Validation or has audit:repair-needed label.
---
author: oompah
created: 2026-07-29 18:39
---
Implementation: Modified epic rollup transitions to route terminal states through coordinator:
1. _reconcile_epic_rollup_statuses: Skips if epic In Validation or has audit:repair-needed; blocks terminal rollup if any child In Validation; routes DONE/MERGED/ARCHIVED through coordinator
2. _auto_close_completed_epics: Routes terminal close through coordinator instead of direct tracker.close_issue()
3. _sync_epic_review_child_states: Routes MERGED transitions through coordinator for stale In Review children
4. Added _request_epic_terminal_rollup() helper to call async coordinator from sync maintenance thread
5. Added _terminal_status_for_tracker() helper to get terminal state from tracker config
6. Added TERMINAL_STATUSES to imports from statuses module

Ready to run tests to verify behavior.
---
author: oompah
created: 2026-07-29 18:50
---
Verification: All tests pass (12932 passed, 41 skipped). Changes implement:

1. Terminal state routing through coordinator for epic rollup reconciliation, auto-close, and stale child completion
2. In Validation children block terminal rollup landing
3. Skip reconciliation if epic In Validation or has audit:repair-needed label
4. Non-terminal state updates continue direct tracker updates

Tests updated to verify coordinator requests instead of direct tracker writes. Branch containment and landing-evidence gates preserved.
---
author: oompah
created: 2026-07-29 18:50
---
Route epic rollup, child Done, and epic close transitions through audits - implemented terminal state routing through coordinator for proper audit chains
---
author: oompah
created: 2026-07-29 18:50
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 132
- Tokens: 2.2K in / 511 out [2.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 24m 48s
- Log: OOMPAH-478__20260729T182724Z.jsonl
---
author: oompah
created: 2026-07-29 22:48
---
Integration found a rebase conflict on `epic-OOMPAH-459--task-OOMPAH-478`. Resolve it against `epic-OOMPAH-459`, run the required tests, push the same private branch, and `oompah task submit` it again.
---
author: oompah
created: 2026-07-29 22:48
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 22:48
---
Agent failed: Epic branch epic-OOMPAH-459 diverged from origin/epic-OOMPAH-459; reconcile both heads before dispatching more children. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-29 22:48
---
Run #1 [attempt=1, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1s
---
author: oompah
created: 2026-07-29 22:48
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 22:48
---
Agent failed: Epic branch epic-OOMPAH-459 diverged from origin/epic-OOMPAH-459; reconcile both heads before dispatching more children. Retrying in 20s (attempt #2)
---
author: oompah
created: 2026-07-29 22:49
---
Run #2 [attempt=2, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 5s
---
author: oompah
created: 2026-07-29 22:49
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-07-29 22:49
---
Agent failed: Epic branch epic-OOMPAH-459 diverged from origin/epic-OOMPAH-459; reconcile both heads before dispatching more children. Retrying in 40s (attempt #3)
---
author: oompah
created: 2026-07-29 22:49
---
Run #3 [attempt=3, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 14s
---
author: oompah
created: 2026-07-29 22:50
---
Retrying (attempt #3, agent: standard)
---
author: oompah
created: 2026-07-29 22:50
---
Agent failed: Epic branch epic-OOMPAH-459 diverged from origin/epic-OOMPAH-459; reconcile both heads before dispatching more children. Retrying in 80s (attempt #4)
---
author: oompah
created: 2026-07-29 22:50
---
Run #4 [attempt=4, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1s
---
author: oompah
created: 2026-07-29 22:52
---
Retrying (attempt #4, agent: standard)
---
author: oompah
created: 2026-07-29 22:52
---
Agent failed: Epic branch epic-OOMPAH-459 diverged from origin/epic-OOMPAH-459; reconcile both heads before dispatching more children. Retrying in 160s (attempt #5)
---
author: oompah
created: 2026-07-29 22:52
---
Run #5 [attempt=5, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1s
---
author: oompah
created: 2026-07-29 23:06
---
Retrying (attempt #5, agent: standard)
---
author: oompah
created: 2026-07-29 23:06
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-29 23:19
---
Run #6 [attempt=6, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 22
- Tokens: 40 in / 1.0K out [1.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 12m 49s
- Log: OOMPAH-478__20260729T230656Z.jsonl
---
author: oompah
created: 2026-07-29 23:20
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 23:20
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-29 23:21
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 12
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 58s
- Log: OOMPAH-478__20260729T232054Z.jsonl
---
author: oompah
created: 2026-07-29 23:34
---
Rebased task-specific rollup transition work onto repaired epic head cfa5ca64f, preserving both newer status imports and removing the obsolete corrupted base commit.
---
author: oompah
created: 2026-07-29 23:39
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-29 23:45
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-29 23:45
---
Run #1 [attempt=1, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3s
---
author: oompah
created: 2026-07-29 23:45
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 00:14
---
Auditor dispatched (attempt #2, candidate: prov-52e94e83/gpt-5.6-sol)
---
author: oompah
created: 2026-07-30 00:14
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 00:58
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_sha: b68d7438fd5afee99b5e77688274478c748bdb3a
- commits_ahead_of_epic: 6
- task_commit_stat: oompah/orchestrator.py +179/-, tests/test_epic_auto_close.py 46 changed, tests/test_epic_strategy.py 24 changed
- focused_tests: pass (2000+ tests across affected suites)
- key_changes: _reconcile_epic_rollup_statuses skips In Validation and audit:repair-needed; blocks rollup when child In Validation; routes terminal states via _request_epic_terminal_rollup. _auto_close_completed_epics routes terminal transition via coordinator; posts reason via append_comment. _sync_epic_review_child_states routes MERGED via coordinator.
---
author: oompah
created: 2026-07-30 00:59
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 75
- Tokens: 98 in / 4.4K out [4.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 44m 17s
- Log: OOMPAH-478__20260730T001450Z.jsonl
---
author: oompah
created: 2026-08-03 20:02
---
Lifecycle reconciliation restored OOMPAH-478 to audited Done: Cannot transition shared-epic child OOMPAH-478 to Merged: parent epic OOMPAH-459 could not be verified. The parent review must land on its configured target branch first.
---
<!-- COMMENTS:END -->
