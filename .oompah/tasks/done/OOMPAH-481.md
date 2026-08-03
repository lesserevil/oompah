---
id: OOMPAH-481
type: feature
status: Done
priority: 1
title: Route automatic archive and intake retirement through Archived audits
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-464
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:29.211296Z'
updated_at: '2026-08-03T20:02:18.172900Z'
work_branch: epic-OOMPAH-459--task-OOMPAH-481
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 37e03dedf4b09d9f40dde2f20036507fba50ed3ba0fb78907074894f9e017853
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:59:19.449025+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation, I need to provide my duplicate\
    \ screening verdict.\n\n## Investigation Summary\n\nI searched the codebase for\
    \ tasks that might be duplicates of OOMPAH-481:\n\n**Search Scope:**\n- All `.oompah/tasks/`\
    \ states (open, backlog, merged, archived)\n- `plans/` directory (37 plan files\
    \ reviewed)\n- Source code for references to: auto-archive, terminal audit, disposition,\
    \ retention, safe retirement, intake retirement, error-task cleanup, external\
    \ issue close\n- Git references for OOMPAH-464, OOMPAH-475, OOMPAH-458 (blockers)\n\
    \n**Key Findings:**\n\n1. **Terminal Audit System**: Already implemented in the\
    \ codebase\n   - `oompah/terminal_audit.py` \u2014 audit record structures\n \
    \  - `oompah/terminal_transition_coordinator.py` \u2014 coordinator\n   - `oompah/terminal_audit_enforcement.py`\
    \ \u2014 auditor\n   - `oompah/terminal_audit_metadata.py` \u2014 metadata storage\n\
    \   - Comprehensive design in `plans/terminal-transition-coordinator.md`\n\n2.\
    \ **Current Auto-Archive**: Exists but bypasses terminal audit system\n   - `oompah/orchestrator.py:21480`\
    \ \u2014 `_auto_archive()` method\n   - Directly archives without audit coordination\n\
    \   - Used for aged Done/Merged items\n\n3. **No Existing Task**: No open, in-progress,\
    \ or recently-merged task covers:\n   - Routing auto-archive maintenance through\
    \ Archived audits\n   - Routing external issue close/archive reconciliation through\
    \ audits\n   - Routing duplicate retirement through audits\n   - Routing error-task\
    \ cleanup through audits\n   - Supply of disposition reason and pre-archive state\n\
    \   - Prevention of repeated requests while audit pending\n   - Unsafe retirement\
    \ with state restoration\n\n4. **Blocker Tasks**: OOMPAH-464, OOMPAH-475, OOMPAH-458\
    \ do not appear in the tracker yet (likely future prerequisites)\n\n---\n\n**Focus\
    \ handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:** OOMPAH-481 is NOT a duplicate. The terminal-transition-coordinator\
    \ system is already implemented (OOMPAH-465, OOMPAH-4"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: d5366bd7-97e6-4901-88d4-006c2a189f76
oompah.work_branch: epic-OOMPAH-459--task-OOMPAH-481
oompah.task_costs:
  total_input_tokens: 2491
  total_output_tokens: 10486
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 2384
      output_tokens: 6172
      cost_usd: 0.0
    unknown:
      input_tokens: 107
      output_tokens: 4314
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 218
    output_tokens: 5606
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:59:19.448217+00:00'
  - profile: default
    model: haiku
    input_tokens: 2166
    output_tokens: 566
    cost_usd: 0.0
    recorded_at: '2026-07-29T18:58:26.294553+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 22
    output_tokens: 635
    cost_usd: 0.0
    recorded_at: '2026-07-30T00:01:24.476162+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 85
    output_tokens: 3679
    cost_usd: 0.0
    recorded_at: '2026-07-30T00:54:19.236202+00:00'
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-459--task-OOMPAH-481
  base_branch: epic-OOMPAH-459
  base_sha: 2e2005cba5b9106029e706db699ca7cfdaa6e3bd
  updated_at: '2026-07-30T00:14:53.849765+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-0a0b17cd406c: '2026-07-30T00:48:56.683557+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-42ba0f38c0a2
    project_id: proj-14849f1b
    task_id: OOMPAH-481
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b4c82deb36ba1c829824ee263c86063f3da398fef045741f106e01a63f130055
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: parent OOMPAH-459 is Merged and its accepted rollup
      contains this previously audited Done child; durable integration-queue/rollup
      evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:23:28.448665+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-481
    target_state: Merged
    evidence_fingerprint: b4c82deb36ba1c829824ee263c86063f3da398fef045741f106e01a63f130055
    audit_ids:
    - audit-73cb5cd3cf84
    kind: override
    applied: true
    retired_at: '2026-08-02T18:23:33.514917+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-73cb5cd3cf84
    project_id: proj-14849f1b
    task_id: OOMPAH-481
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a77b2088442c4e04cbdfceefaa2357d2e3d61c7ee20a204f057af3e92707a5e9
    attempts:
    - version: 1
      attempt_id: attempt-987beac3b8e9
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a77b2088442c4e04cbdfceefaa2357d2e3d61c7ee20a204f057af3e92707a5e9
      created_at: '2026-07-30T00:00:25.335407+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T00:00:25.335407+00:00'
      branch_key: epic-OOMPAH-459--task-OOMPAH-481
      ended_at: '2026-07-30T00:01:26.747963+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-0a0b17cd406c
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a77b2088442c4e04cbdfceefaa2357d2e3d61c7ee20a204f057af3e92707a5e9
      created_at: '2026-07-30T00:14:45.850859+00:00'
      provider_id: prov-52e94e83
      model: gpt-5.6-sol
      started_at: '2026-07-30T00:14:45.850859+00:00'
      branch_key: epic-OOMPAH-459--task-OOMPAH-481
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-07-30T00:48:56.683354+00:00'
      ended_at: '2026-07-30T00:48:56.683354+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T00:00:17.284993+00:00'
    updated_at: '2026-07-30T00:48:56.683354+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-987beac3b8e9
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a77b2088442c4e04cbdfceefaa2357d2e3d61c7ee20a204f057af3e92707a5e9
    created_at: '2026-07-30T00:00:25.335407+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T00:00:25.335407+00:00'
    branch_key: epic-OOMPAH-459--task-OOMPAH-481
    ended_at: '2026-07-30T00:01:26.747963+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-0a0b17cd406c
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a77b2088442c4e04cbdfceefaa2357d2e3d61c7ee20a204f057af3e92707a5e9
    created_at: '2026-07-30T00:14:45.850859+00:00'
    provider_id: prov-52e94e83
    model: gpt-5.6-sol
    started_at: '2026-07-30T00:14:45.850859+00:00'
    branch_key: epic-OOMPAH-459--task-OOMPAH-481
    candidate_rotation_count: 1
---
## Summary

Implementation scope

Update auto-archive maintenance, external issue close/archive reconciliation, duplicate retirement, error-task cleanup, and other automatic archive_issue/status=Archived calls to request an Archived audit. Supply retention or structured disposition reason and pre-archive state. Do not repeatedly request archive while an audit is pending. On unsafe retirement, restore the recorded prior state or use the coordinator failure classification. Existing archived upgrade records stay grandfathered.

Tests

Cover aged Done/Merged auto-archive, recent item, active review/agent/retry, external issue close, duplicate with source reference, missing disposition evidence, repeated maintenance ticks, failed tracker writes, unsafe restoration, and grandfathered Archived records. Run archive/intake/error-watcher tests and make test.

Acceptance criteria

No automatic path hides unresolved work in Archived; valid retirement remains bounded/idempotent and produces a concise durable audit comment.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:57
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:59
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 56, Tool calls: 26
- Tokens: 218 in / 5.6K out [5.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 34s
- Log: OOMPAH-481__20260729T015749Z.jsonl
---
author: oompah
created: 2026-07-29 18:29
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 18:30
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-29 18:30
---
## Understanding and Plan

This task requires routing automatic archive operations (auto-archive maintenance, external issue close/archive reconciliation, duplicate retirement, error-task cleanup) through Archived audits instead of direct archive_issue calls.

**Key requirements:**
- All automatic archive_issue/status=Archived calls must request an Archived audit
- Include retention/disposition reason and pre-archive state in audit requests
- Prevent repeated archive requests while an audit is pending
- On unsafe retirement, restore prior state or use failure classification
- Grandfather existing archived records

**Planned approach:**
1. Discover auto-archive code paths (likely in maintenance, intake, archive, and error-watcher modules)
2. Identify archive_issue calls that bypass audit logging
3. Implement audit request wrapper that checks pending state
4. Add disposition reason and pre-archive state capture
5. Add tests for aged archives, pending audits, failed writes, unsafe restoration

Starting discovery phase now.
---
author: oompah
created: 2026-07-29 18:34
---
## Discovery

Found relevant auto-archive code in:
1. **orchestrator.py (lines 21679-21760)** - _do_auto_archive() loops through closed issues and calls tracker.archive_issue() directly
2. **stalled_task_watchdog.py** - archives error tasks via tracker.archive_issue()
3. **release_pick_migration.py** - archives duplicate children via tracker.archive_issue()

Current audit infrastructure:
- **terminal_transition_coordinator.py** - provides request_transition() API for requesting terminal states
- **terminal_audit_enforcement.py** - grandfathers existing terminal tasks and tracks pending audits
- Evidence fingerprints are created via compute_evidence_fingerprint()
- Audit comments are generated by the auditor; we provide requirements_text (disposition reason)

Task: Route all three auto-archive paths through request_transition() instead of direct archive_issue() calls. Need to:
- Create wrapper function to prevent repeated audit requests while one is pending
- Supply disposition reason (e.g. 'aged Done/Merged auto-archive') as requirements_text
- Capture pre-archive state from issue.state
- Add tests for repeated maintenance ticks, failed writes, unsafe restoration

Next: Implement archive-through-audit wrapper.
---
author: oompah
created: 2026-07-29 18:57
---
## Implementation Complete

Successfully routed all automatic archive operations through Archived audits:

**Changes made:**
1. Created oompah/archived_audit_requests.py module with request_archived_audit() helper function
2. Updated orchestrator._do_auto_archive() to queue audits instead of direct archive
3. Updated stalled_task_watchdog._run() to queue audits for error-task cleanup  
4. Updated release_pick_migration._archive_child_task() to queue audits for duplicate retirement

**Key features:**
- All audit requests include disposition reason (e.g. 'Aged Done/Merged auto-archive')
- Pre-archive state captured in audit record
- Prevents duplicate audits by checking for pending Archived audits with same fingerprint
- Issues transition to 'In Validation' state while audit is pending
- All operations properly handle failures and log issues

**Tests updated and passing:**
- test_archived_audit_requests.py (5 new tests)
- test_orchestrator_handlers.py auto_archive tests
- test_error_watcher.py (117 tests)
- test_release_pick_migration.py (updated 6 archive-related tests)

Total: 133 tests passing, no failures. Ready for review and integration.
---
author: oompah
created: 2026-07-29 18:58
---
Routed automatic archive operations through Archived audits with disposition reasons and pre-archive state capture
---
author: oompah
created: 2026-07-29 18:58
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 129
- Tokens: 2.2K in / 566 out [2.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 28m 31s
- Log: OOMPAH-481__20260729T183010Z.jsonl
---
author: oompah
created: 2026-07-29 22:48
---
Integration found a rebase conflict on `epic-OOMPAH-459--task-OOMPAH-481`. Resolve it against `epic-OOMPAH-459`, run the required tests, push the same private branch, and `oompah task submit` it again.
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
- Exit: error, Duration: 4s
---
author: oompah
created: 2026-07-29 22:49
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 22:49
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
- Exit: error, Duration: 1s
---
author: oompah
created: 2026-07-29 22:50
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-07-29 22:50
---
Run #3 [attempt=3, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 3s
---
author: oompah
created: 2026-07-29 22:50
---
Agent failed: Epic branch epic-OOMPAH-459 diverged from origin/epic-OOMPAH-459; reconcile both heads before dispatching more children. Retrying in 40s (attempt #3)
---
author: oompah
created: 2026-07-29 22:51
---
Retrying (attempt #3, agent: standard)
---
author: oompah
created: 2026-07-29 22:51
---
Agent failed: Epic branch epic-OOMPAH-459 diverged from origin/epic-OOMPAH-459; reconcile both heads before dispatching more children. Retrying in 80s (attempt #4)
---
author: oompah
created: 2026-07-29 22:51
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
- Exit: error, Duration: 4s
---
author: oompah
created: 2026-07-29 23:06
---
Retrying (attempt #5, agent: standard)
---
author: oompah
created: 2026-07-29 23:07
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-29 23:19
---
Run #6 [attempt=6, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 0, Tool calls: 40
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 13m 6s
- Log: OOMPAH-481__20260729T230714Z.jsonl
---
author: oompah
created: 2026-07-29 23:41
---
Rebased automatic Archived-audit routing onto the repaired epic base; preserved and hardened retry/coalescing behavior; full gate passed (13628 passed, 7 skipped).
---
author: oompah
created: 2026-07-30 00:00
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 00:00
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 00:00
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 00:01
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 11
- Tokens: 22 in / 635 out [657 total]
- Cost: $0.0000
- Exit: terminated, Duration: 58s
- Log: OOMPAH-481__20260730T000034Z.jsonl
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
created: 2026-07-30 00:48
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: 2e2005cba5b9106029e706db699ca7cfdaa6e3bd
- origin_branch_head: 2e2005cba5b9106029e706db699ca7cfdaa6e3bd
- epic_head: 65df7489f845e7def17ee6612060a0bc6130ba82
- task_commits: f793f91f4, 2e2005cba
- archived_audit_requests_tests: 6 passed
- github_intake_bridge_tests: 57 passed
- release_pick_migration_tests: 58 passed
- stalled_task_watchdog_tests: 79 passed
- terminal_transition_coordinator_tests: 102 passed
- terminal_audit_tests: 69 passed
- orchestrator_handlers_tests: 267 passed
- error_watcher_tests: 130 passed
- managed_tracker_state_branch_guard_tests: 19 passed
- callsites: orchestrator._do_auto_archive; stalled_task_watchdog; release_pick_migration; github_intake_bridge (close + cancel)
---
author: oompah
created: 2026-07-30 00:54
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 63
- Tokens: 85 in / 3.7K out [3.8K total]
- Cost: $0.0000
- Exit: terminated, Duration: 39m 28s
- Log: OOMPAH-481__20260730T001456Z.jsonl
---
author: oompah
created: 2026-08-02 18:23
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: parent OOMPAH-459 is Merged and its accepted rollup contains this previously audited Done child; durable integration-queue/rollup evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.
---
<!-- COMMENTS:END -->
