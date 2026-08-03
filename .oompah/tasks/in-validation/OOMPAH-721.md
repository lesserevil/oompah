---
id: OOMPAH-721
type: task
status: In Validation
priority: null
title: Do not escalate completed duplicate preflights as implementation work
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T14:39:16.938367Z'
updated_at: '2026-08-03T15:55:41.686082Z'
work_branch: OOMPAH-721
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/681
review_number: '681'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2d9cf1ef6da5b257011f4cfaf6c43cfb8cdd40a0b1fe94a02ee38a3d5a089a4b
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T14:43:11.552891+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active task in the authoritative corpus covers this\
    \ duplicate-preflight exit/escalation bug. Closest reviewed tasks\u2014OOMPAH-156,\
    \ OOMPAH-168, and OOMPAH-170\u2014are archived and address different behavior.\n\
    Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none\n\nEvidence: No active task in the authoritative corpus covers\
    \ this duplicate-preflight exit/escalation bug. Closest reviewed tasks\u2014OOMPAH-156,\
    \ OOMPAH-168, and OOMPAH-170\u2014are archived and address different behavior."
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
oompah.task_costs:
  total_input_tokens: 51880
  total_output_tokens: 10048
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 51836
      output_tokens: 1202
      cost_usd: 0.0
    unknown:
      input_tokens: 44
      output_tokens: 8846
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50598
    output_tokens: 879
    cost_usd: 0.0
    recorded_at: '2026-08-03T14:43:11.552089+00:00'
  - profile: default
    model: haiku
    input_tokens: 1238
    output_tokens: 323
    cost_usd: 0.0
    recorded_at: '2026-08-03T15:01:34.681167+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 1235
    cost_usd: 0.0
    recorded_at: '2026-08-03T15:35:01.793870+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 38
    output_tokens: 7611
    cost_usd: 0.0
    recorded_at: '2026-08-03T15:54:06.963645+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-721__20260803T144231Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-721
    source_sha: 99d33e120ffafe28b5790438072bfa9e74f88974
    completed_at: '2026-08-03T14:43:11.558589+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-721
  head_sha: 145972d505913bad93562ffc96a96870724d0dee
  submitted_at: '2026-08-03T15:12:28.036171+00:00'
  updated_at: '2026-08-03T15:12:28.036171+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/681
oompah.review_number: '681'
oompah.work_branch: OOMPAH-721
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-356e0211afcd: '2026-08-03T15:53:45.082368+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-721
    target_state: Done
    evidence_fingerprint: 379d47075f1b47d3755ea6cf340cbb7cf008516ee910b5924613b1d3a205e5c2
    audit_ids:
    - audit-e9645dfd935b
    kind: result
    applied: true
    retired_at: '2026-08-03T15:53:45.082381+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-721
    audit_id: audit-e9645dfd935b
    attempt_id: attempt-356e0211afcd
    target_state: Done
    evidence_fingerprint: 379d47075f1b47d3755ea6cf340cbb7cf008516ee910b5924613b1d3a205e5c2
    status: In Validation
    audit_ids:
    - audit-e9645dfd935b
    applied: true
    created_at: '2026-08-03T15:53:45.082399+00:00'
    applied_at: '2026-08-03T15:53:49.992174+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-e9645dfd935b
    project_id: proj-14849f1b
    task_id: OOMPAH-721
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 379d47075f1b47d3755ea6cf340cbb7cf008516ee910b5924613b1d3a205e5c2
    attempts:
    - version: 1
      attempt_id: attempt-1098f1c4f8cd
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 379d47075f1b47d3755ea6cf340cbb7cf008516ee910b5924613b1d3a205e5c2
      created_at: '2026-08-03T15:32:35.592639+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T15:32:35.592639+00:00'
      branch_key: OOMPAH-721
      failure_classification: infrastructure_error
      ended_at: '2026-08-03T15:35:05.771565+00:00'
      failure_reason: normal
      next_retry_at: '2026-08-03T15:35:15.771535+00:00'
    - version: 1
      attempt_id: attempt-356e0211afcd
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 379d47075f1b47d3755ea6cf340cbb7cf008516ee910b5924613b1d3a205e5c2
      created_at: '2026-08-03T15:36:24.100287+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-03T15:36:24.100287+00:00'
      branch_key: OOMPAH-721
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-08-03T15:53:45.082202+00:00'
      ended_at: '2026-08-03T15:53:45.082202+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T15:31:55.010817+00:00'
    updated_at: '2026-08-03T15:53:45.082202+00:00'
  - version: 1
    audit_id: audit-ce15aece1fdf
    project_id: proj-14849f1b
    task_id: OOMPAH-721
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 379d47075f1b47d3755ea6cf340cbb7cf008516ee910b5924613b1d3a205e5c2
    attempts:
    - version: 1
      attempt_id: attempt-d3ed62d52bb9
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 379d47075f1b47d3755ea6cf340cbb7cf008516ee910b5924613b1d3a205e5c2
      created_at: '2026-08-03T15:55:35.859899+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T15:55:35.859899+00:00'
      branch_key: OOMPAH-721
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T15:31:55.010817+00:00'
    updated_at: '2026-08-03T15:55:35.859899+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-1098f1c4f8cd
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 379d47075f1b47d3755ea6cf340cbb7cf008516ee910b5924613b1d3a205e5c2
    created_at: '2026-08-03T15:32:35.592639+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T15:32:35.592639+00:00'
    branch_key: OOMPAH-721
    failure_classification: infrastructure_error
    ended_at: '2026-08-03T15:35:05.771565+00:00'
    failure_reason: normal
    next_retry_at: '2026-08-03T15:35:15.771535+00:00'
  - version: 1
    attempt_id: attempt-356e0211afcd
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 379d47075f1b47d3755ea6cf340cbb7cf008516ee910b5924613b1d3a205e5c2
    created_at: '2026-08-03T15:36:24.100287+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-03T15:36:24.100287+00:00'
    branch_key: OOMPAH-721
    candidate_rotation_count: 1
  - version: 1
    attempt_id: attempt-d3ed62d52bb9
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 379d47075f1b47d3755ea6cf340cbb7cf008516ee910b5924613b1d3a205e5c2
    created_at: '2026-08-03T15:55:35.859899+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T15:55:35.859899+00:00'
    branch_key: OOMPAH-721
---
## Summary

Live reproduction (2026-08-03): automatically filed epic-staleness tasks EXOCOMP-240 and EXOCOMP-241 entered In Progress under Focus: Duplicate Investigator. EXOCOMP-241's screening run exited normally without closing the task, but the generic worker-exit path escalated it from standard to deep and relaunched the same Duplicate Investigator instead of recording the screening result and handing the still-active task to the rebase/merge-conflict focus. This regresses the two-stage behavior previously specified by OOMPAH-217 and wastes increasingly expensive agents on implementation work outside the duplicate-screening role.

Implementation scope:
- Route every model-backed duplicate-preflight exit through the dedicated screening completion path before generic retry/escalation logic, including auto-filed maintenance/rebase tasks and providers that return no structured duplicate verdict.
- A non-duplicate/indeterminate normal exit must atomically clear the preflight claim, persist a revision-aware screened result (or bounded retry only within the screening subsystem), return the task to Open, and dispatch a fresh implementation session with the appropriate rebase focus.
- A Duplicate Investigator must never execute the rebase or other implementation, and generic standard-to-deep escalation must never retain duplicate_preflight=true.
- Preserve confirmed-duplicate archival, changed-task fingerprint invalidation, crash retry limits, authority revocation, and concurrency accounting.

Required tests:
- Reproduce EXOCOMP-241: normal preflight exit without closing an auto-filed rebase task, then prove no generic escalation occurs and the next worker is a rebase specialist with duplicate_preflight=false.
- Cover missing/malformed structured verdicts, confirmed duplicates, changed fingerprints, provider failure, restart recovery, and exact running/preflight counters.
- Assert the duplicate prompt cannot perform implementation and task comments clearly distinguish screening from implementation handoff.
- Run focused duplicate-screening/orchestrator/maintenance suites and make test.

Acceptance criteria:
- EXOCOMP-240/241-style tasks cannot loop or escalate under Duplicate Investigator.
- Screening either archives a confirmed duplicate or hands an active task to a new correctly focused implementation agent exactly once.
- No stale preflight claim or duplicate running entry remains after handoff.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 14:42
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 14:42
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 14:43
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.6K in / 879 out [51.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 46s
- Log: OOMPAH-721__20260803T144231Z.jsonl
---
author: oompah
created: 2026-08-03 14:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 14:43
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-03 14:44
---
**Understanding & Plan:**

OOMPAH-721 requires fixing duplicate-preflight screening handoff to prevent infinite loops. Currently, when a Duplicate Investigator agent exits normally from screening, the generic escalation logic relaunches the same agent instead of handing off to a rebase specialist.

**Key changes needed:**
1. Route all model-backed duplicate-preflight exits through a dedicated screening completion path
2. On non-duplicate/indeterminate normal exit: atomically clear preflight claim, persist result, return task to Open, dispatch correct focus
3. Ensure Duplicate Investigator never executes implementation work
4. Prevent generic standard-to-deep escalation from retaining duplicate_preflight=true

**Approach:**
- Find worker exit/escalation handling logic
- Identify duplicate screening completion paths
- Implement dedicated preflight completion path
- Add tests for EXOCOMP-241-style scenarios
- Verify no stale preflight claims or duplicate running entries remain

Starting discovery now.
---
author: oompah
created: 2026-08-03 14:51
---
**Discovery: Root Cause Identified**

Found the regression in orchestrator.py:

Current behavior (_finish_duplicate_preflight_sync):
- When screening finishes with NO_DUPLICATE verdict, it:
  1. Completes the screening record ✓
  2. Saves the record ✓
  3. Returns outcome='checked' ✗ (but doesn't hand off)

The problem:
- No handoff comment is posted (focus handoff: duplicate_detector)
- No focus-complete:duplicate_detector label is added
- Task stays in Open but without proper handoff markers
- Next scheduler tick doesn't know to dispatch implementation with correct focus
- Generic escalation logic then takes over instead of dispatching implementation

The fix requires:
1. After NO_DUPLICATE verdict, post handoff comment with verdict block
2. Add focus-complete:duplicate_detector label
3. Immediately dispatch fresh implementation agent with appropriate focus (rebase/general)
4. Ensure duplicate_preflight claim is cleared before implementation dispatch
5. Add tests for EXOCOMP-241-style scenarios (no-dup screen → rebase dispatch, no escalation)

Key files:
- oompah/orchestrator.py: _finish_duplicate_preflight_sync, _handle_duplicate_preflight_exit
- oompah/focus.py: duplicate_detector focus definition
- oompah/duplicate_screening.py: result parsing and record management

Starting implementation now.
---
author: oompah
created: 2026-08-03 15:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 70
- Tokens: 1.2K in / 323 out [1.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 48s
- Log: OOMPAH-721__20260803T144352Z.jsonl
---
author: oompah
created: 2026-08-03 15:01
---
Direct-owner correction: the live EXOCOMP-241 first run emitted structured duplicate_preflight_result=inconclusive, but it was registered/commented as ordinary Agent dispatched and then passed through generic standard-to-deep retry. The draft NO_DUPLICATE-only post-exit dispatch does not cover that reproduction; it also selects focus before a completion marker, passes focus.name as override_profile, and bypasses normal candidate/claim/concurrency dispatch. Owner is replacing it with a regression at the dispatch classification/claim-propagation boundary plus bounded screening retry/handoff tests.
---
author: oompah
created: 2026-08-03 15:12
---
Owner implementation complete at 145972d505913bad93562ffc96a96870724d0dee. Root cause: auto-filed rebase tasks start in Needs Rebase and therefore are ordinary implementation dispatches; generic focus triage nevertheless selected the scheduler-owned duplicate_detector, registering its read-only verdict run as implementation and sending its exit through standard-to-deep escalation. Fix: make duplicate_detector an immutable reserved focus, select it only through the dedicated duplicate-preflight RunningEntry boundary, give its prompt an explicit read-only scheduler contract, and keep reserved foci out of generic handoff mutation instructions. Regression proves EXOCOMP-241-style Needs Rebase work selects merge_conflict, ordinary entries cannot receive Duplicate Investigator, dedicated preflight entries still do, and user focus overrides cannot unreserve it. Checks: terminal mutation scan passed; 180 focus/preflight tests passed at exact rebased head; 300 adjacent focus-triage/auditor/duplicate-detection/epic-strategy tests passed before the conflict-free rebase.
---
author: oompah
created: 2026-08-03 15:12
---
Reserve Duplicate Investigator for scheduler-owned preflight; prevent ordinary maintenance tasks from entering duplicate-only escalation loops.
---
author: oompah
created: 2026-08-03 15:21
---
Branch quality gate passed for `145972d505913bad93562ffc96a96870724d0dee` using `make test` in 408.0s. Review creation may proceed.
---
author: oompah
created: 2026-08-03 15:32
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-03 15:32
---
YOLO: merged PR #681.
---
author: oompah
created: 2026-08-03 15:32
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 15:32
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 15:35
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 2, Tool calls: 0
- Tokens: 6 in / 1.2K out [1.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 22s
- Log: OOMPAH-721__20260803T153247Z.jsonl
---
author: oompah
created: 2026-08-03 15:35
---
Auditor attempt ended: auditor exited (normal) without a result. A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-03 15:36
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-03 15:36
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 15:53
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_commit: 145972d505913bad93562ffc96a96870724d0dee
- focus_tests: 140 passed
- preflight_tests: 40 passed
- duplicate_suite: 243 passed
- orchestrator_maintenance: 928 passed
- terminal_mutation_scan: 8 passed
- full_gate: make test passed in 408s (trusted evidence)
- pr_status: merged PR #681
---
author: oompah
created: 2026-08-03 15:54
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 62, Tool calls: 41
- Tokens: 38 in / 7.6K out [7.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 17m 41s
- Log: OOMPAH-721__20260803T153631Z.jsonl
---
author: oompah
created: 2026-08-03 15:55
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 15:55
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
