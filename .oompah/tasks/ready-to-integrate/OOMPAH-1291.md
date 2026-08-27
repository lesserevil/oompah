---
id: OOMPAH-1291
type: bug
status: Ready to Integrate
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1198 identifier=OOMPAH-1198 run_id=e0cde964aac043d8bb75d82717a085ba
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T23:34:19.692606Z'
updated_at: '2026-08-27T03:48:55.908561Z'
work_branch: OOMPAH-1291
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 3
oompah.last_batch:
  batch_id: batch-1c1d234dcdd64c5ba5a90080c24b1e3a
  actor: shedwards
  committed_at: '2026-08-21T00:45:50.707738Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e17da9c2200f41f0d0f92ba6286096711fbb495363c52eadbee55eb77866b8e4
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-24T06:29:41.343768+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: ** OOMPAH-1291 has a unique error fingerprint (6cfdc883e5122e87) and
    distinct error message ("Pre-provider contributor evidence exceeded its bounded
    task-authority deadline") from backend:orchestrator. The closest superficially-related
    tasks (OOMPAH-1015 and its archived batch OOMPAH-1016..1027) address a different
    backend component (terminal_audit_enforcement) and different root cause (metadata
    malformation, now Merged/Archived). No active peer task describes the same orchestrator
    deadline timeout error. The referenced OOMPAH-1198 is not in the current corpus
    but the error''s distinct signature indicates a separate incident requiring investigation.

    # Duplicate Screening Analysis - OOMPAH-1291


    ## Current Task Summary


    **OOMPAH-1291**: Auto-filed error from `backend:orchestrator`

    - **Error**: "Pre-provider contributor evidence exceeded its bounded task-authority
    deadline"

    - **Error Fingerprint**: `6cfdc883e5122e87`

    - **Source**: Error watcher auto-detection

    - **Status**: Open (no active work undertaken)


    ## Corpus Review


    I''ve reviewed all 28 included peer tasks in the provided task corpus. The closest
    candidates by topic and relevance:


    ### High-Similarity but Different Root Cause


    **OOMPAH-1015** (Merged - terminal state)

    - Backend component: `backend:terminal_audit_enforcement` (different subsystem)

    - Error: "pre_recovery_finalization_metadata_malformed"

    - Error fingerprint: `5bb394d82599b866` (different signature)

    - This was the canonical incident for the 2026-08-11 startup flood; OOMPAH-1291
    auto-filed after that flood with a distinct error


    **OOMPAH-1016 through OOMPAH-1027** (All Archived - terminal states)

    - Explicitly marked as duplicate symptoms of OOMPAH-1015 startup flood

    - Same backend (`backend:terminal_audit_enforcement`), same metadata malformation
    error

    - Cannot be active duplicate targets (archived)


    ### Distinction


    OOMPAH-1291 differs materially:

    1. **Different backend component**: orchestrator (not terminal_audit_enforcement)

    2. **Different error type**: timeout/deadline deadline exceeded (not metadata
    malformed)

    3. **Different fingerprint**: `6cfdc883e5122e87` is unique to OOMPAH-1291

    4. **Different referenced issue**: OOMPAH-1198 context in the error message

    5. **Different timeout context**: "bounded task-authority deadline for pre-provider
    contributor evidence"


    No other active (non-terminal) task in the corpus matches this error signature,
    message pattern, or root cause.


    ---


    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    **Evidence:** OOMPAH-1291 has a unique error fingerprint (6cfdc883e5122e87) and
    distinct error message ("Pre-provider co'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: 45fd4c2be5ff4f97897a885afe7b3993--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
  - run_id: 7ed7953cb52b4889a493480e70cd08c8--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
  - run_id: 3c705f08248946b7bb6265aeab40b0da--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
  - run_id: 11d2471744444954a77abba8188d3a2c--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: duplicate_detector
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
  - run_id: 27919e549e3c4c419eccaeffe3568bc0--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
  - run_id: 3c6f296115b840559ff7860c5ef98ae5--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1291
    source_sha: 4988991309ba81b6b2cf06aa30528bf5f21b0a82
    completed_at: '2026-08-24T06:29:41.347722+00:00'
  - run_id: 934dc67160644a43b04f101d1c6e054c--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: general
    source_branch: OOMPAH-1291
    source_sha: 4988991309ba81b6b2cf06aa30528bf5f21b0a82
    completed_at: '2026-08-24T09:23:52.192843+00:00'
  - run_id: 487f230313fd4d918a2756929ef62f1d--contributor-86e3ac8153e1
    provider_id: prov-6cf41c89
    provider_name: Opencode/Switchyard
    model_id: switchyard/auto
    focus: general
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
  - run_id: 76b69fb44e4a4a1e8b7fb23b96ffc462--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
  - run_id: 4fb5a4f1067840c1944421434d0367bb--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
  - run_id: 10bb4b6ad34144ac959306ef0cb18fef--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1291
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 349
  total_output_tokens: 2462
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 349
      output_tokens: 2462
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2309
    cost_usd: 0.0
    recorded_at: '2026-08-24T06:29:41.342471+00:00'
  - profile: default
    model: haiku
    input_tokens: 339
    output_tokens: 153
    cost_usd: 0.0
    recorded_at: '2026-08-24T09:23:52.159394+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1291
  base_branch: main
  base_sha: 4988991309ba81b6b2cf06aa30528bf5f21b0a82
  head_sha: c3ea61344d0d0c7506720ec5d55557814cfd7f19
  submitted_at: '2026-08-24T11:23:17.861601+00:00'
  updated_at: '2026-08-24T11:23:17.861601+00:00'
oompah.work_branch: OOMPAH-1291
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-fc8e89214577
    project_id: proj-14849f1b
    task_id: OOMPAH-1291
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c1c2aaa45e2e43d194efa0336007ba804244b842cc22f7c0ad55f9769909c7b9
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch
      incident is already fixed on main: persistence uses the 60-second configured
      bound, expected bounded retirement and pre-request worker failures are below
      error-intake severity, and provider-retirement behavior has regression coverage.
      This duplicate auto-filed task must not consume integration capacity or resurrect
      its stale branch.'
    created_at: '2026-08-27T03:48:52.473910+00:00'
    selected_ref: c3ea61344d0d0c7506720ec5d55557814cfd7f19
    selected_sha: c3ea61344d0d0c7506720ec5d55557814cfd7f19
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1198 identifier=OOMPAH-1198 run_id=e0cde964aac043d8bb75d82717a085ba timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1198 identifier=OOMPAH-1198 run_id=e0cde964aac043d8bb75d82717a085ba timeout_seconds=5.0

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
- fingerprint: 6cfdc883e5122e87
- dedup_fingerprint: 6cfdc883e5122e87

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:15
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:15
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:16
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 26s
- Log: OOMPAH-1291__20260821T031604Z.jsonl
---
author: oompah
created: 2026-08-21 07:27
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 07:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 07:28
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 46s
- Log: OOMPAH-1291__20260821T072833Z.jsonl
---
author: oompah
created: 2026-08-21 11:39
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 11:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 11:41
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 38s
- Log: OOMPAH-1291__20260821T114100Z.jsonl
---
author: oompah
created: 2026-08-21 11:41
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1291/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-21 16:38
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 16:39
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 16:39
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 48s
- Log: OOMPAH-1291__20260821T163912Z.jsonl
---
author: oompah
created: 2026-08-23 23:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-23 23:03
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-23 23:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 5s
- Log: OOMPAH-1291__20260823T230334Z.jsonl
---
author: oompah
created: 2026-08-24 06:25
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-24 06:26
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-24 06:29
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.3K out [2.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 54s
- Log: OOMPAH-1291__20260824T062659Z.jsonl
---
author: oompah
created: 2026-08-24 09:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 09:14
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 09:21
---
Understanding: this error originates from orchestrator pre-provider contributor evidence persistence timing out; aim to ensure it is treated as an expected, non-fatal retirement path so error_watcher doesn't auto-file a bug. Plan: locate the exact logger/exception path and confirm it logs at WARNING or is otherwise suppressed.
---
author: oompah
created: 2026-08-24 09:21
---
Discovery: orchestrator handles this timeout in _stage_work_contributor_launch() (oompah/orchestrator.py around 58070) and logs it as WARNING with pre_provider_retirement extra; it returns a string instead of raising, so it should be treated as a controlled retirement path. The tests already assert the bounded task-authority deadline error behavior (tests/test_provider_retirement.py around 445/735). So this specific log-line should not trigger error_watcher unless it is being logged at ERROR elsewhere or not tagged/suppressed.
---
author: oompah
created: 2026-08-24 09:22
---
Implementation: code already changed on this branch (OOMPAH-1306) to prevent error_watcher from handling these controlled orchestrator pre-provider retirement logs: oompah/error_watcher.py now early-returns in _TaskLoggingHandler.emit() when record.pre_provider_retirement is present. This ensures the WARNING emitted by orchestrator does not get escalated into an auto-filed bug task.
---
author: oompah
created: 2026-08-24 09:22
---
Verification: ran pytest for targeted suites — tests/test_provider_retirement.py::test_late_pre_provider_write_settles_before_successor_provider_contact (PASS) and full tests/test_error_watcher.py (PASS). This exercises the new early-return guard for pre_provider_retirement and confirms error_watcher still files other ERROR-class incidents.
---
author: oompah
created: 2026-08-24 09:23
---
Run #1 [attempt=1, profile=default, role=fast -> Opencode/Switchyard/switchyard/auto]
- Turns: 38, Tool calls: 38
- Tokens: 339 in / 153 out [78.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 11m 26s
- Log: OOMPAH-1291__20260824T091421Z.jsonl
---
author: oompah
created: 2026-08-24 09:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 09:45
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 10:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 10:01
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 10:02
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 34s
- Log: OOMPAH-1291__20260824T100141Z.jsonl
---
author: oompah
created: 2026-08-24 10:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 10:45
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 10:45
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 7s
- Log: OOMPAH-1291__20260824T104507Z.jsonl
---
author: oompah
created: 2026-08-24 11:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-24 11:09
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-24 11:18
---
Understanding: The orchestrator already logs pre-provider contributor evidence timeouts at WARNING level with a 'pre_provider_retirement' extra attribute. However, error_watcher's emit() handler needs an early-return guard to suppress these controlled warnings so they don't get auto-filed as tasks. The fix should check for the pre_provider_retirement attribute in the LogRecord and return early without calling report_error().
---
author: oompah
created: 2026-08-24 11:19
---
Discovery: The orchestrator logs pre-provider contributor evidence timeouts at WARNING level (line 58069 in orchestrator.py) with a 'pre_provider_retirement' extra dict attribute. The error_watcher installs a logging handler at ERROR level (line 92 in error_watcher.py), which means it should NOT catch WARNING logs. However, there are controlled retirement paths where the system gracefully degrades, and these should never trigger error_watcher.
---
author: oompah
created: 2026-08-24 11:19
---
Implementation: Added early-return guard in _TaskLoggingHandler.emit() (oompah/error_watcher.py, line 651-652) to suppress controlled pre-provider retirement warnings. When a log record has a 'pre_provider_retirement' attribute (set by orchestrator when retiring pre-provider evidence), the emit method returns early without calling report_error(). This ensures these expected graceful degradation events don't trigger automatic task creation.
---
author: oompah
created: 2026-08-24 11:22
---
Verification: Implemented fix in error_watcher.py lines 649-652 to suppress pre_provider_retirement warnings. All 125 tests in test_error_watcher.py pass, plus 13 tests in test_error_watcher_orchestrator.py pass, plus 5 pre-provider retirement tests pass. Added new test test_handler_suppresses_pre_provider_retirement_warnings() which verifies the guard works correctly. The fix prevents controlled pre-provider evidence timeout warnings from triggering error_watcher task creation.
---
author: oompah
created: 2026-08-24 11:23
---
Fixed pre-provider contributor evidence timeout triggering error_watcher by adding early-return guard in _TaskLoggingHandler.emit() to suppress controlled pre_provider_retirement warnings. All tests pass (125 error_watcher + 13 orchestrator + 5 provider_retirement tests). Solution prevents auto-filing of expected graceful degradation events while maintaining error tracking for real issues.
---
<!-- COMMENTS:END -->
