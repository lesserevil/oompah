---
id: OOMPAH-737
type: task
status: In Validation
priority: null
title: Keep health and graceful cutover responsive during terminal lifecycle reconciliation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T20:06:54.610285Z'
updated_at: '2026-08-03T22:06:22.399398Z'
work_branch: OOMPAH-737
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/693
review_number: '693'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8c7ca7cc15be7da68de2f1a25d6e40c9495ab01df5429c37fa842e2d02adeb5c
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T20:15:16.866522+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** All 31 similarity-matched candidates from the corpus\
    \ are in Archived state and therefore ineligible as active duplicate targets.\
    \ No active (Open, In Progress, Backlog, or In Review) task in the corpus addresses\
    \ the terminal lifecycle reconciliation performance regression described in OOMPAH-737.\
    \ The task covers a distinct issue: moving bulk lifecycle reconciliation off the\
    \ HTTP request path during graceful cutover to keep health/state endpoints responsive.\n\
    Looking at the supplied project task corpus, I need to evaluate whether OOMPAH-737\
    \ is a duplicate of any active (non-terminal) task.\n\n**OOMPAH-737** addresses\
    \ a critical regression where terminal lifecycle reconciliation blocks HTTP endpoints\
    \ during graceful cutover, making `/healthz` and `/api/v1/state` unresponsive\
    \ for minutes and causing `make restart` to timeout.\n\n## Analysis of Candidates\n\
    \nThe corpus includes 31 similarity-matched tasks. I've reviewed each against\
    \ the requirements:\n\n**All 31 candidates are in terminal state (Archived):**\n\
    - OOMPAH-1, OOMPAH-2, OOMPAH-10, OOMPAH-11, OOMPAH-14, OOMPAH-15, OOMPAH-156,\
    \ OOMPAH-157, OOMPAH-158, OOMPAH-16, OOMPAH-160, OOMPAH-161, OOMPAH-162, OOMPAH-165,\
    \ OOMPAH-166, OOMPAH-167, OOMPAH-169, OOMPAH-17, OOMPAH-171, OOMPAH-172, OOMPAH-176,\
    \ OOMPAH-177, OOMPAH-178, OOMPAH-179, OOMPAH-180, OOMPAH-181, OOMPAH-182, OOMPAH-183,\
    \ OOMPAH-186, OOMPAH-188, OOMPAH-192\n\nPer the requirements: \"Exclude every\
    \ candidate in a terminal state (Done, Merged, or Archived). A completed task\
    \ is historical context, not an active duplicate target.\"\n\nThe candidates cover\
    \ release management, epic strategies, GitHub integration, task validation, and\
    \ miscellaneous operational issues\u2014none address the specific regression of\
    \ terminal lifecycle reconciliation blocking the HTTP event loop during cutover.\n\
    \n---\n\n**Focus handoff: duplicate_detector**\n\n**Duplicate preflight verdict:\
    \ no_duplicate**\n\n**Matches: none**\n\n**Evidence:** All 31 similarity-matched\
    \ candidates from the corpus are in Archived state and therefore ineligible as\
    \ active duplicate targets. No active (Open, In Progress, Backlog, or In Review)\
    \ task in the corpus addresses the terminal lifecycle reconciliation performance\
    \ regression described in OOMPAH-737. The task covers a distinct issue: moving\
    \ bulk lifecycle reconciliation off the HTTP request path during graceful cutover\
    \ to keep health/state endpoints responsive."
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
  total_input_tokens: 10
  total_output_tokens: 1961
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1961
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1961
    cost_usd: 0.0
    recorded_at: '2026-08-03T20:15:16.864091+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-737__20260803T200951Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-737
    source_sha: 42da24c2617b86610838c8097eaec2ede58ec44c
    completed_at: '2026-08-03T20:15:16.891355+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-737
  head_sha: 2fba254fa752e0fcb5bdcfe80b9ccb739b507339
  submitted_at: '2026-08-03T20:50:10.181276+00:00'
  updated_at: '2026-08-03T20:50:10.181276+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/693
oompah.review_number: '693'
oompah.work_branch: OOMPAH-737
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-fe377e05acb9: '2026-08-03T22:06:15.729137+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-737
    target_state: Done
    evidence_fingerprint: b25b3c554ad5dcabef0c9d82cde7fed09ac413add71f1bc8f60c3fb574c388d9
    audit_ids:
    - audit-c5a768bff9d5
    kind: result
    applied: true
    retired_at: '2026-08-03T22:06:15.729149+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-737
    audit_id: audit-c5a768bff9d5
    attempt_id: attempt-fe377e05acb9
    target_state: Done
    evidence_fingerprint: b25b3c554ad5dcabef0c9d82cde7fed09ac413add71f1bc8f60c3fb574c388d9
    status: In Validation
    audit_ids:
    - audit-c5a768bff9d5
    applied: true
    created_at: '2026-08-03T22:06:15.729168+00:00'
    applied_at: '2026-08-03T22:06:20.231913+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c5a768bff9d5
    project_id: proj-14849f1b
    task_id: OOMPAH-737
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b25b3c554ad5dcabef0c9d82cde7fed09ac413add71f1bc8f60c3fb574c388d9
    attempts:
    - version: 1
      attempt_id: attempt-fe377e05acb9
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b25b3c554ad5dcabef0c9d82cde7fed09ac413add71f1bc8f60c3fb574c388d9
      created_at: '2026-08-03T21:24:06.787998+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T21:24:06.787998+00:00'
      branch_key: OOMPAH-737
      verdict: pass
      completed_at: '2026-08-03T22:06:15.728901+00:00'
      ended_at: '2026-08-03T22:06:15.728901+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T21:21:04.199551+00:00'
    updated_at: '2026-08-03T22:06:15.728901+00:00'
  - version: 1
    audit_id: audit-0346802ed738
    project_id: proj-14849f1b
    task_id: OOMPAH-737
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b25b3c554ad5dcabef0c9d82cde7fed09ac413add71f1bc8f60c3fb574c388d9
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T21:21:04.199551+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-fe377e05acb9
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b25b3c554ad5dcabef0c9d82cde7fed09ac413add71f1bc8f60c3fb574c388d9
    created_at: '2026-08-03T21:24:06.787998+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T21:24:06.787998+00:00'
    branch_key: OOMPAH-737
---
## Summary

Live regression observed during make restart on 2026-08-03 after deploying fae232ee6. The graceful cutover drained all workers and the service exec reached the new revision, but resume synchronously reconciled dozens of lifecycle-incompatible shared-epic children from Merged to Done. Each tracker mutation took roughly 5–6 seconds; for more than four minutes the listening service returned no bytes even from /healthz or /api/v1/state. scripts/canonical_cli_cutover.py therefore timed out POST /api/v1/orchestrator/resume and reported that cutover failed, even though the new instance later became healthy at the intended revision. This regresses OOMPAH-350's HTTP-loop isolation guarantee and makes OOMPAH-676's safe cutover result ambiguous.\n\nImplementation scope:\n- Move bulk terminal lifecycle reconciliation off the HTTP request/event-loop path used by resume and startup readiness.\n- Make reconciliation bounded, resumable, idempotent, and observable, with progress persisted between batches.\n- Keep /healthz and /api/v1/state responsive while reconciliation runs; expose degraded/migrating progress without misreporting the build identity.\n- Make the cutover wrapper distinguish an accepted candidate exec plus busy migration from an unchanged old service, and prevent a resume transport timeout from falsely reporting rollback/failure when the candidate is authoritative.\n- Preserve exact lifecycle fencing, tracker comments, audit metadata, state-branch writes, and per-record failure isolation.\n\nRelevant code: oompah/terminal_audit_enforcement.py lifecycle reconciliation, orchestrator resume/startup scheduling, oompah/server.py lifecycle endpoints and health, scripts/canonical_cli_cutover.py resolution logic, and Makefile restart tests.\n\nRequired tests:\n- Seed dozens of incompatible shared-epic children with a deliberately slow tracker; resume must return promptly and /healthz plus /api/v1/state must stay responsive while batches drain.\n- Prove every row converges exactly once across restart mid-batch, tracker failure, duplicate resume, and concurrent state reads.\n- Reproduce the live cutover: candidate exec succeeds, resume response times out or is delayed by migration, and the wrapper must identify the candidate revision/instance without false rollback or error.\n- Preserve OOMPAH-350 scheduler isolation and OOMPAH-676 graceful worker-drain semantics; run focused lifecycle, terminal enforcement, cutover, health, and Makefile restart suites plus make test.\n\nAcceptance criteria:\n- No terminal-reconciliation workload can make health/state endpoints unresponsive.\n- make restart reports success when the intended candidate is healthy, even if post-exec migration is still progressing.\n- Reconciliation remains fail-closed, durable, bounded, and restart-safe, with actionable diagnostics only for rows that cannot converge.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 20:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 20:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 20:15
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 27s
- Log: OOMPAH-737__20260803T200951Z.jsonl
---
author: oompah
created: 2026-08-03 20:18
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 20:18
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-03 20:18
---
Understanding: terminal lifecycle reconciliation currently runs synchronously during resume/startup and can starve the HTTP loop. I will trace reconciliation, orchestrator scheduling, health/state reporting, and canonical cutover resolution; move only the bulk work to bounded durable background batches, preserve fencing/audit/error isolation, add regression tests, verify focused suites, then commit/push/submit.
---
author: oompah
created: 2026-08-03 20:19
---
Discovery: TerminalAuditEnforcement.initialize() performs the full tracker scan/recovery/persist synchronously in _run_terminal_audit_enforcement, while merged-label maintenance also contains independent shared-epic child reconciliation. The server already exposes cached state and build identity; I’m tracing startup/resume ordering and cutover resolution to isolate the blocking path and preserve existing fencing/audit semantics.
---
author: oompah
created: 2026-08-03 20:26
---
Implementation: Added versioned lifecycle reconciliation state with pending/completed/failed rows, persisted counters/cursor/errors, bounded batch processing, per-row locks, and non-blocking progress snapshots. Terminal-audit startup now defers legacy shared-epic repair; the orchestrator schedules coalesced background batches and exposes terminal_lifecycle_reconciliation in maintenance/state. Added OOMPAH_TERMINAL_LIFECYCLE_RECONCILIATION_BATCH_SIZE configuration. Cutover now treats a candidate health/state identity as authoritative and ignores a post-candidate resume transport failure.
---
author: oompah
created: 2026-08-03 20:33
---
Verification so far: 75 focused terminal-enforcement/cutover tests pass; 292 adjacent event-loop/config/build-identity/auth/restart-helper tests pass. Added metadata-write interruption coverage showing restart recovery finalizes the audit ledger without a duplicate Done mutation. A make setup attempt was blocked by the environment's astral-uv DBus transient-scope error, so I’m continuing with the existing project Python environment and will report that gate limitation separately.
---
author: oompah
created: 2026-08-03 20:47
---
Verification: focused lifecycle, cutover, and config suites pass (194 tests); affected event/server suites passed earlier (499 tests, 1 expected xfail); Granian e2e rerun passes 4/4. Terminal mutation scan passes 8/8 allowlisted and py_compile/git diff checks pass. The full parallel test phase reached 15,188 passed with one transient Granian restart failure that passed in isolation; Makefile setup/test prerequisites remain blocked by the environment uv transient-scope DBus error.
---
author: oompah
created: 2026-08-03 20:49
---
Implementation: lifecycle repair now uses a persisted per-row queue with pre-mutation conflict intent, bounded background batches, restart-safe metadata completion, retry/degraded diagnostics, and serialized audit initialization. Orchestrator startup/full-sync paths defer the repair and publish progress through cached state; healthz remains identity-only. Cutover commits a proven candidate before treating resume transport failure as non-fatal.
---
author: oompah
created: 2026-08-03 20:50
---
Completion: pushed branch OOMPAH-737 at 2fba254fa752e0fcb5bdcfe80b9ccb739b507339. Delivered deferred bounded lifecycle reconciliation, durable restart-safe per-row progress and failure isolation, responsive state observability, and candidate-authoritative cutover resume handling. Working tree is clean and branch matches origin.
---
author: oompah
created: 2026-08-03 20:50
---
Deferred terminal lifecycle reconciliation to bounded durable background batches; kept health/state responsive and made candidate-authoritative cutovers tolerate delayed resume transport.
---
author: oompah
created: 2026-08-03 20:50
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 168
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 32m 49s
- Log: OOMPAH-737__20260803T201821Z.jsonl
---
author: oompah
created: 2026-08-03 21:06
---
Branch quality gate passed for `2fba254fa752e0fcb5bdcfe80b9ccb739b507339` using `make test` in 413.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-03 21:21
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-03 21:21
---
YOLO: merged PR #693.
---
author: oompah
created: 2026-08-03 21:24
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 21:24
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 22:06
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- commit_sha: 2fba254fa752e0fcb5bdcfe80b9ccb739b507339
- merge_commit_sha: 3cdf7d41f3928c06545d1b58e88614226ede7ab3
- pr_number: 693
- files_changed: .env.example, oompah/config.py, oompah/orchestrator.py, oompah/terminal_audit_enforcement.py, scripts/canonical_cli_cutover.py, tests/test_config.py, tests/test_lifecycle_cli_sync_integration.py, tests/test_terminal_audit_enforcement.py
- focused_test_totals: terminal_audit_enforcement=50, lifecycle_cli_sync_integration=27, config=117, terminal_audit_health=44, terminal_audit_observability=19, terminal_audit+health_api+scanner+workspace_recovery=48, state/blocking/restart/canonical=97, orchestrator=78, dispatch=101, scanner=15, restart_api+auth_health+lifespan_abort=57
- unrelated_failure: tests/test_makefile_setup.py::test_non_gate_test_setup_still_installs_declared_dependencies (Makefile unchanged in commit; auditor worktree uses task-venv path)
- prior_full_gate: make test PASS 413.3s at 2fba254fa (recorded in task comments)
- acceptance_endpoint_responsive: test_lifecycle_progress_read_does_not_wait_for_slow_tracker_mutation
- acceptance_cutover_authoritative: test_candidate_resume_timeout_does_not_false_fail_cutover
- acceptance_durable_restart_safe: test_lifecycle_reconciliation_batches_are_durable_and_restart_safe + test_lifecycle_reconciliation_finishes_after_status_write_metadata_failure
- acceptance_failure_isolation: test_lifecycle_reconciliation_isolates_tracker_failures_and_retries
- acceptance_deferred_startup: test_initialize_can_defer_lifecycle_reconciliation
---
<!-- COMMENTS:END -->
