---
id: OOMPAH-1316
type: bug
status: Merged
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1196 identifier=OOMPAH-1196 run_id=45e6fe9e17414df8adda05d62cf48ee4
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:48:11.061409Z'
updated_at: '2026-08-25T22:47:56.190667Z'
work_branch: OOMPAH-1316
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/903
review_number: '903'
review_head: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
merged_at: null
oompah.lifecycle_revision: 8
oompah.last_batch:
  batch_id: batch-05f0739579694f67a5b19b240bad80a4
  actor: shedwards
  committed_at: '2026-08-21T01:07:48.555641Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 285f4d3f707f257cb7cd6eaca55f7f2cc524ddcf7aad296779f47fcba8a5f2a9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T04:07:48.873435+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1316 reports a bounded task-authority deadline\
    \ timeout in backend:orchestrator, which does not match any active task in the\
    \ corpus. All similar candidates (primarily OOMPAH-1000\u20131027) are in terminal\
    \ states and describe different issues: workflow/epic handling, terminal-audit\
    \ enforcement metadata, or completed recovery work. The error domain (orchestrator\
    \ vs. terminal_audit_enforcement) and symptom (authority deadline vs. malformed\
    \ metadata) are distinct from all reviewed tasks. No active duplicate can be confirmed\
    \ from the available corpus.\nLooking at OOMPAH-1316 and analyzing the supplied\
    \ project task corpus for potential duplicates.\n\n## Duplicate Investigation\n\
    \n**OOMPAH-1316** reports an error from `backend:orchestrator`:\n- Error: \"Pre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline\"\n- Issue\
    \ ID referenced: OOMPAH-1196\n- Timeout: 5 seconds\n- Status: Open\n- Auto-filed\
    \ by error_watcher\n\n### Corpus Analysis\n\nReviewing the 29 included similarity\
    \ candidates in the corpus:\n\n**Active (non-terminal) tasks:** Only OOMPAH-1316\
    \ itself (status: Open)\n\n**Archived/terminal tasks reviewed:**\n- OOMPAH-1000\
    \ through OOMPAH-1012: Various workflow, epic, and terminal-audit issues \u2014\
    \ all Merged/Done\n- OOMPAH-1014: Orphaned terminal-audit authority \u2014 Merged\n\
    - OOMPAH-1015: Legacy terminal-override compatibility (terminal_audit_enforcement\
    \ malformed metadata) \u2014 Merged\n- OOMPAH-1016 through OOMPAH-1027: Startup\
    \ flood duplicates of OOMPAH-1015 \u2014 all Archived with explicit notes like\
    \ \"Erroneous auto-file duplicate from the 2026-08-11 05ed11f22 malformed-ledger\
    \ startup flood; OOMPAH-1015 is the canonical incident\"\n- OOMPAH-1, OOMPAH-10,\
    \ OOMPAH-164: Various older tasks \u2014 all Archived\n\n### Key Findings\n\n\
    1. **No active duplicate exists.** The only non-terminal task in the corpus is\
    \ OOMPAH-1316 itself.\n\n2. **Different error domain.** OOMPAH-1316 reports an\
    \ error from `backend:orchestrator` about \"bounded task-authority deadline.\"\
    \ The closest similar issues in the corpus (OOMPAH-1015, OOMPAH-1016\u20131027)\
    \ report `backend:terminal_audit_enforcement` errors about \"pre_recovery_finalization_metadata_malformed\"\
    \ \u2014 a different problem.\n\n3. **Cross-reference unresolved.** OOMPAH-1316's\
    \ error message references OOMPAH-1196, but that task is not in the supplied corpus\
    \ (which included only 29 of 726 similarity candidates). That reference may point\
    \ to a related but distinct issue.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-1316\
    \ reports a bounded task"
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
oompah.work_contributors:
  runs:
  - run_id: f8c4634572d24818a5ca1d438fb65d62--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1316
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T04:07:48.898133+00:00'
  - run_id: 5cea23f4c35a4786a29cdb3b5f988c65--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1316
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 23
  total_output_tokens: 6198
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2127
      cost_usd: 0.0
    unknown:
      input_tokens: 13
      output_tokens: 4071
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2127
    cost_usd: 0.0
    recorded_at: '2026-08-21T04:07:48.872530+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 13
    output_tokens: 4071
    cost_usd: 0.0
    recorded_at: '2026-08-25T22:45:20.170543+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1316
  base_branch: main
  base_sha: c7b3911883a90c1b5805204a430926eb1c6f53b8
  head_sha: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
  submitted_at: '2026-08-21T08:56:20.710336+00:00'
  updated_at: '2026-08-24T07:34:12.148174+00:00'
oompah.work_branch: OOMPAH-1316
oompah.review_url: https://github.com/lesserevil/oompah/pull/903
oompah.review_number: '903'
oompah.target_branch: main
oompah.review_head: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-a359395fa5a8
    project_id: proj-14849f1b
    task_id: OOMPAH-1316
    digest: e5830b5262a5a540a044e98f8ab3f3aa0137dc7203c37296372e15d6ef26a534
  - version: 1
    audit_id: audit-e3508d682e48
    project_id: proj-14849f1b
    task_id: OOMPAH-1316
    digest: e5830b5262a5a540a044e98f8ab3f3aa0137dc7203c37296372e15d6ef26a534
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1316","audit-a359395fa5a8","attempt-ed79a8ebb7d6"]': '2026-08-25T22:45:00.322706+00:00'
    '["proj-14849f1b","OOMPAH-1316","audit-e3508d682e48","attempt-c79e80584251"]': '2026-08-25T22:47:45.608672+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1316
    target_state: Done
    evidence_fingerprint: e5830b5262a5a540a044e98f8ab3f3aa0137dc7203c37296372e15d6ef26a534
    workflow_revision: null
    selected_ref: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
    selected_sha: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
    landing_revision: null
    audit_ids:
    - audit-a359395fa5a8
    kind: result
    applied: true
    retired_at: '2026-08-25T22:45:00.322723+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1316
    target_state: Merged
    evidence_fingerprint: e5830b5262a5a540a044e98f8ab3f3aa0137dc7203c37296372e15d6ef26a534
    workflow_revision: null
    selected_ref: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
    selected_sha: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
    landing_revision: null
    audit_ids:
    - audit-e3508d682e48
    kind: result
    applied: true
    retired_at: '2026-08-25T22:47:45.608701+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1316
    audit_id: audit-a359395fa5a8
    attempt_id: attempt-ed79a8ebb7d6
    target_state: Done
    evidence_fingerprint: e5830b5262a5a540a044e98f8ab3f3aa0137dc7203c37296372e15d6ef26a534
    status: In Validation
    audit_ids:
    - audit-a359395fa5a8
    kind: result
    applied: true
    created_at: '2026-08-25T22:45:00.322734+00:00'
    applied_at: '2026-08-25T22:45:09.292841+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1316
    audit_id: audit-e3508d682e48
    attempt_id: attempt-c79e80584251
    target_state: Merged
    evidence_fingerprint: e5830b5262a5a540a044e98f8ab3f3aa0137dc7203c37296372e15d6ef26a534
    status: Merged
    audit_ids:
    - audit-e3508d682e48
    kind: result
    applied: true
    created_at: '2026-08-25T22:47:45.608714+00:00'
    applied_at: '2026-08-25T22:47:54.586667+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a359395fa5a8
    project_id: proj-14849f1b
    task_id: OOMPAH-1316
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e5830b5262a5a540a044e98f8ab3f3aa0137dc7203c37296372e15d6ef26a534
    attempts:
    - version: 1
      attempt_id: attempt-ed79a8ebb7d6
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e5830b5262a5a540a044e98f8ab3f3aa0137dc7203c37296372e15d6ef26a534
      created_at: '2026-08-25T22:40:51.572267+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-25T22:40:51.572267+00:00'
      branch_key: OOMPAH-1316
      selected_ref: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
      selected_sha: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
      verdict: pass
      completed_at: '2026-08-25T22:45:00.322517+00:00'
      ended_at: '2026-08-25T22:45:00.322517+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-25T22:36:39.734117+00:00'
    eligible_at: '2026-08-25T22:36:39.734117+00:00'
    selected_ref: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
    selected_sha: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
    updated_at: '2026-08-25T22:45:00.322517+00:00'
  - version: 1
    audit_id: audit-e3508d682e48
    project_id: proj-14849f1b
    task_id: OOMPAH-1316
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e5830b5262a5a540a044e98f8ab3f3aa0137dc7203c37296372e15d6ef26a534
    attempts:
    - version: 1
      attempt_id: attempt-c79e80584251
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e5830b5262a5a540a044e98f8ab3f3aa0137dc7203c37296372e15d6ef26a534
      created_at: '2026-08-25T22:45:26.989803+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-25T22:45:26.989803+00:00'
      branch_key: OOMPAH-1316
      selected_ref: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
      selected_sha: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
      verdict: pass
      completed_at: '2026-08-25T22:47:45.608505+00:00'
      ended_at: '2026-08-25T22:47:45.608505+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-25T22:36:39.734117+00:00'
    prerequisite_audit_id: audit-a359395fa5a8
    selected_ref: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
    selected_sha: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
    updated_at: '2026-08-25T22:47:45.608505+00:00'
    eligible_at: '2026-08-25T22:45:00.322517+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ed79a8ebb7d6
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e5830b5262a5a540a044e98f8ab3f3aa0137dc7203c37296372e15d6ef26a534
    created_at: '2026-08-25T22:40:51.572267+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-25T22:40:51.572267+00:00'
    branch_key: OOMPAH-1316
    selected_ref: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
    selected_sha: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
  - version: 1
    attempt_id: attempt-c79e80584251
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e5830b5262a5a540a044e98f8ab3f3aa0137dc7203c37296372e15d6ef26a534
    created_at: '2026-08-25T22:45:26.989803+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-25T22:45:26.989803+00:00'
    branch_key: OOMPAH-1316
    selected_ref: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
    selected_sha: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1196 identifier=OOMPAH-1196 run_id=45e6fe9e17414df8adda05d62cf48ee4 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1196 identifier=OOMPAH-1196 run_id=45e6fe9e17414df8adda05d62cf48ee4 timeout_seconds=5.0

### Expected Behavior
The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: e6fd4c20f6c3b668
- dedup_fingerprint: e6fd4c20f6c3b668

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 04:06
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 04:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 04:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 19s
- Log: OOMPAH-1316__20260821T040717Z.jsonl
---
author: oompah
created: 2026-08-21 08:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 08:37
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 08:44
---
UNDERSTANDING: The issue is a timeout in backend:orchestrator when trying to persist pre-provider contributor evidence (provider/model identity) to the tracker. The timeout occurs in _stage_work_contributor_launch() when asyncio.wait_for() exceeds persistence_timeout (default ~5sec based on control/termination timeouts, but can be configured). This error is being auto-filed by error_watcher because it's currently logged as ERROR level. The fix involves either: (1) improving tracker write performance, (2) increasing the timeout gracefully, (3) changing the log level/handling so error_watcher doesn't treat it as a reportable error, or (4) documenting this as expected behavior. Starting investigation of error_watcher and timeout configuration.
---
author: oompah
created: 2026-08-21 08:45
---
DISCOVERY: Root cause identified in oompah/orchestrator.py:_stage_work_contributor_launch(). When writing pre-provider contributor evidence (provider/model identity) times out (line 58066), a logger.error() is called. This log message gets caught by error_watcher (oompah/error_watcher.py) which auto-files it as a task. However, this timeout is an expected failure scenario during task authority transitions/retirement - it's handled gracefully (returns an error message, releases task authority). Similar cancelled timeout case (line 58102) already uses logger.warning(). Fix: change logger.error() to logger.warning() to prevent error_watcher from filing this as a task.
---
author: oompah
created: 2026-08-21 08:54
---
IMPLEMENTATION: Changed logger.error() to logger.warning() on line 58066 of oompah/orchestrator.py. This timeout occurs when pre-provider contributor evidence write takes longer than the bounded deadline during task authority transitions. This is an expected, handled failure mode (already returns error message, releases authority gracefully). The similar cancelled timeout case already uses logger.warning(). By logging at WARNING instead of ERROR, error_watcher no longer auto-files this as a task.
---
author: oompah
created: 2026-08-21 08:54
---
VERIFICATION: All tests pass. Ran: (1) test_pre_provider_evidence_timeout_releases_task_authority - PASSED, (2) test_contributor_evidence_takes_project_lock_before_policy_lock - PASSED, (3) all 21 tests in test_provider_retirement.py - PASSED, (4) all 146 error_watcher related tests - PASSED. The fix maintains backward compatibility while preventing spurious error task auto-filing.
---
author: oompah
created: 2026-08-21 08:56
---
Fixed contributor evidence timeout being auto-filed as error task by changing log level from ERROR to WARNING. This timeout is an expected, gracefully-handled failure during task authority transitions. All related tests pass (21 provider_retirement tests, 146 error_watcher tests).
---
author: oompah
created: 2026-08-21 13:27
---
Branch quality gate passed for `7e932a894d16d6f5530dbf43a2eebb93db8684ba` using `make test` in 184.1s. Review creation may proceed.
---
author: oompah
created: 2026-08-24 11:16
---
Branch quality gate passed for `7e932a894d16d6f5530dbf43a2eebb93db8684ba` using `make test` in 193.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-25 22:36
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-25 22:40
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-25 22:41
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-25 22:45
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- fix_location: oompah/orchestrator.py:58066
- fix_description: logger.error() changed to logger.warning() for pre-provider contributor evidence timeout message
- error_watcher_filter_level: logging.ERROR (error_watcher.py:92)
- test_coverage: test_pre_provider_evidence_timeout_releases_task_authority in tests/test_provider_retirement.py
- quality_gate_sha: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
- quality_gate_result: passed
- quality_gate_command: make test
- quality_gate_duration_seconds: 193.9
---
author: oompah
created: 2026-08-25 22:45
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 25, Tool calls: 15
- Tokens: 13 in / 4.1K out [4.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 25s
- Log: OOMPAH-1316__20260825T224114Z.jsonl
---
author: oompah
created: 2026-08-25 22:45
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-25 22:45
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-25 22:47
---
Audit PASS — Merged

Fix verified. `logger.error()` was changed to `logger.warning()` at oompah/orchestrator.py:58066 for the pre-provider contributor evidence timeout message. error_watcher.py:92 filters at logging.ERROR, so WARNING-level logs no longer trigger auto-filing. Test `test_pre_provider_evidence_timeout_releases_task_authority` covers the timeout path. Full gate `make test` passed at exact SHA 7e932a894d16d6f5530dbf43a2eebb93db8684ba (authoritative, 193.9s). All acceptance criteria satisfied. PASS.

Safe evidence:
- fix_location: oompah/orchestrator.py:58066
- fix_description: logger.error() changed to logger.warning() for pre-provider contributor evidence timeout message
- error_watcher_filter_level: logging.ERROR (error_watcher.py:92)
- test_coverage: test_pre_provider_evidence_timeout_releases_task_authority in tests/test_provider_retirement.py
- quality_gate_sha: 7e932a894d16d6f5530dbf43a2eebb93db8684ba
- quality_gate_result: passed
- quality_gate_command: make test
- quality_gate_duration_seconds: 193.9
- prior_audit_result: pass (attempt #1, same evidence)
---
<!-- COMMENTS:END -->
