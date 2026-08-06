---
id: OOMPAH-833
type: task
status: In Validation
priority: null
title: Bootstrap durable ACP command-result delivery onto main
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-810
labels: []
assignee: null
created_at: '2026-08-05T15:59:15.045452Z'
updated_at: '2026-08-06T02:06:13.146945Z'
work_branch: OOMPAH-833
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/727
review_number: '727'
review_head: c8e6efcd265bb3cb18ae46213b0adbcbb3e088c1
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 779fe688ccb7347578c5880808cb71d52c21e909a221be6514cd43f9674d8e09
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T00:01:41.009155+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: OOMPAH-833 is explicitly a follow-up porting task to the completed OOMPAH-810.
    The task corpus confirms OOMPAH-810 reached Done status and was integrated into
    OOMPAH-763 (commit bb42de1e7). OOMPAH-833''s purpose is to port that same logical
    repair to the main branch after OOMPAH-810''s completion, not to duplicate or
    re-solve the same problem. The coordination notes and hard_start_dependency relationship
    confirm this is intentional dependent work. No other active (Open) tasks in the
    corpus describe the same bootstrap-to-main porting scope.

    Looking at the current task corpus, I need to compare OOMPAH-833 against existing
    tasks to determine if it''s a duplicate.


    ## Analysis


    **Current Task: OOMPAH-833**

    - Title: "Bootstrap durable ACP command-result delivery onto main"

    - Status: Open

    - Description: Port the logical repair from OOMPAH-810 (which is implemented on
    OOMPAH-763) onto the main branch


    **Key Dependency: OOMPAH-810**

    - Title: "Return completed auditor command results without stranding the ACP session"

    - Status: Done

    - Coordination note: "OOMPAH-810 was integrated into OOMPAH-763 at bb42de1e71f355a8f0eb2c4c0ddd958715b646e6"

    - Listed as a hard_start_dependency for OOMPAH-833


    **Relationship:**

    The task corpus explicitly shows that OOMPAH-833 depends on OOMPAH-810 as a hard
    dependency. The coordination comments confirm OOMPAH-810 has been completed and
    integrated into the OOMPAH-763 branch. OOMPAH-833''s scope is specifically to
    **port** the same changes from OOMPAH-810 onto the main branch, not to duplicate
    or re-implement the work.


    The tasks are distinct:

    - **OOMPAH-810**: Implements the ACP command-result delivery fix (completed, integrated
    to OOMPAH-763)

    - **OOMPAH-833**: Ports that same fix to the main branch (follow-up work, currently
    Open)


    All other tasks in the corpus with similarity (OOMPAH-1 through OOMPAH-184) are
    either Archived or Done, making them ineligible as active duplicate candidates.


    ---


    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: OOMPAH-833 is explicitly a follow-up porting task to the completed OOMPAH-810.
    The task corpus confirms OOMPAH-810 reached Done status and was integrated into
    OOMPAH-763 (commit bb42de1e7). OOMPAH-833''s purpose is to port that same logical
    repair to the main branch after OOMPAH-810''s completion, not to duplicate or
    re-solve the same problem. The coordination notes and hard_start_dependency relationship
    confirm this is intentional dependent work. No other active (Open) tasks in the
    corpus de'
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
  total_output_tokens: 1489
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1489
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1489
    cost_usd: 0.0
    recorded_at: '2026-08-06T00:01:41.007106+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-833__20260806T000009Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-833
    source_sha: b98ebb40d269ebeb7a134dc43add36bf782d9402
    completed_at: '2026-08-06T00:01:41.026473+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-833
  head_sha: c8e6efcd265bb3cb18ae46213b0adbcbb3e088c1
  submitted_at: '2026-08-06T00:23:09.385751+00:00'
  updated_at: '2026-08-06T00:23:09.385751+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/727
oompah.review_number: '727'
oompah.work_branch: OOMPAH-833
oompah.target_branch: main
oompah.review_head: c8e6efcd265bb3cb18ae46213b0adbcbb3e088c1
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-f067cc122bc4: '2026-08-06T02:06:02.815962+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-833
    target_state: Done
    evidence_fingerprint: 6fe4f370885f73f29d404c268d27208fe600e43712eab92a23ded20d7a4d1134
    audit_ids:
    - audit-3ef17a87895f
    kind: result
    applied: true
    retired_at: '2026-08-06T02:06:02.815973+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-833
    audit_id: audit-3ef17a87895f
    attempt_id: attempt-f067cc122bc4
    target_state: Done
    evidence_fingerprint: 6fe4f370885f73f29d404c268d27208fe600e43712eab92a23ded20d7a4d1134
    status: In Validation
    audit_ids:
    - audit-3ef17a87895f
    applied: true
    created_at: '2026-08-06T02:06:02.815987+00:00'
    applied_at: '2026-08-06T02:06:10.476961+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-3ef17a87895f
    project_id: proj-14849f1b
    task_id: OOMPAH-833
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6fe4f370885f73f29d404c268d27208fe600e43712eab92a23ded20d7a4d1134
    attempts:
    - version: 1
      attempt_id: attempt-f067cc122bc4
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 6fe4f370885f73f29d404c268d27208fe600e43712eab92a23ded20d7a4d1134
      created_at: '2026-08-06T02:01:58.829424+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-06T02:01:58.829424+00:00'
      branch_key: OOMPAH-833
      verdict: pass
      completed_at: '2026-08-06T02:06:02.815784+00:00'
      ended_at: '2026-08-06T02:06:02.815784+00:00'
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-06T02:01:28.702889+00:00'
    updated_at: '2026-08-06T02:06:02.815784+00:00'
  - version: 1
    audit_id: audit-56a0e0d0e1da
    project_id: proj-14849f1b
    task_id: OOMPAH-833
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6fe4f370885f73f29d404c268d27208fe600e43712eab92a23ded20d7a4d1134
    attempts: []
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-06T02:01:28.702889+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-f067cc122bc4
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6fe4f370885f73f29d404c268d27208fe600e43712eab92a23ded20d7a4d1134
    created_at: '2026-08-06T02:01:58.829424+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-06T02:01:58.829424+00:00'
    branch_key: OOMPAH-833
---
## Summary

Triggered by: OOMPAH-810.

OOMPAH-810 is implemented on the systemic OOMPAH-763 branch, but the running main server must execute many expensive worker and auditor gates before that root can land. Live OOMPAH-523 proves the completed-command/result-delivery race affects ordinary implementation workers as well as terminal auditors. After OOMPAH-810 reaches reviewed Done, port the same logical repair patch-equivalently onto then-current main.

Implementation scope:
- Apply only the reviewed ACP run_command completion, bounded result delivery, liveness/result_pending state, exact-once retirement/retry, and observability changes from OOMPAH-810.
- Preserve validation-resource arbitration, command deadlines, cancellation, output redaction/paging, per-session authority, exact worker/audit identity, and current main-only lifecycle fixes.
- Do not pull unrelated durable-workflow epic changes or weaken auditor/task-handoff authority.

Required tests:
- Run the complete OOMPAH-810 focused ACP/tool-liveness/result-output/provider-retirement matrix against the standalone composition.
- Replay both OOMPAH-793 auditor and OOMPAH-523 implementation-worker command-exit races, including child exit concurrent with stall scan, and prove exactly one bounded tool_result or precise delivery-timeout outcome.
- Prove a successful expensive gate is not blindly rerun when durable compatible evidence is safely reusable, while failed/unknown outcomes remain fail-closed.
- Run terminal mutation and secret scans plus the configured full Makefile gate.

Acceptance criteria:
- The standalone reviewed head contains no unrelated systemic-epic work and is merged to main.
- A controlled make restart deploys the exact main revision after active agents drain.
- A live worker and terminal auditor each receive command completion without an immediate accumulated-idle stall, duplicate retry, hidden provider, or stale alert.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 23:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 23:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 00:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.5K out [1.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 54s
- Log: OOMPAH-833__20260806T000009Z.jsonl
---
author: oompah
created: 2026-08-06 00:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 00:02
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 00:02
---
Understanding: I will identify the reviewed OOMPAH-810 ACP command-result delivery changes, compare them with current main, port only the completion/delivery/liveness/retirement/observability logic, add regression coverage for worker and auditor races, run focused checks plus the configured gate, then commit, push, and submit.
---
author: oompah
created: 2026-08-06 00:03
---
Implementation: applied only reviewed OOMPAH-810 commit bb42de1e7 onto current main; the patch is limited to oompah/acp_agent.py, acp_tools.py, api_agent.py, orchestrator.py, tool_liveness.py and the two focused regression suites. It preserves current-main validation leases, deadlines, cancellation, redaction/paging, authority, and lifecycle code because no systemic-epic files were brought over.
---
author: oompah
created: 2026-08-06 00:11
---
Verification: focused ACP/tool-liveness/result-output tests now pass 35/35, including a new deterministic child-exit versus stall-scan race proving exactly one result-delivery owner and exactly-once acknowledgement. The adjacent ACP/provider/retirement/lifecycle matrix passed 561/573; 12 failures are environment-only writes to read-only operator paths (/home/shedwards/.oompah/agent-logs and native-validation-guards). Terminal mutation scan passed (8/8 allowlisted) and direct secret scan passed; Make wrappers remain blocked by the same host guard/runtime setup.
---
author: oompah
created: 2026-08-06 00:18
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 81
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 15m 53s
- Log: OOMPAH-833__20260806T000219Z.jsonl
---
author: oompah
created: 2026-08-06 00:18
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-06 00:18
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 00:19
---
Understanding: resuming the preserved reviewed OOMPAH-810-equivalent ACP delivery backport. I will verify the recovery checkpoint contains only scoped completion/liveness/retirement work and its race coverage, run the current focused matrix, then create the task commit, push it, and submit the exact head.
---
author: oompah
created: 2026-08-06 00:21
---
Discovery: recovery head 8cfac3a8 is a clean, patch-equivalent port of reviewed OOMPAH-810 onto b98ebb40. It changes only the seven scoped ACP/liveness/observability/test files; the added standalone regression deterministically races child exit with stall inspection and permits exactly one delivery acknowledgement. The current Make test-setup is blocked before test execution by a host validation guard chmod on its read-only service lock directory; the configured task virtualenv is now unavailable, so no guard bypass was attempted.
---
author: oompah
created: 2026-08-06 00:22
---
Implementation: committed c8e6efcd2 (and pushed as origin/OOMPAH-833). It ports only the reviewed command completion-to-delivery lifecycle: bounded result_pending handoff, exact-once provider acknowledgement, explicit delivery deadline/stall state, opaque health metrics, and worker/auditor output/race regressions. No validation, authority, cancellation, redaction, or lifecycle behavior outside that scope changed.
---
author: oompah
created: 2026-08-06 00:22
---
Verification: the preserved focused ACP/tool-liveness/result-output suite passed 35/35; adjacent ACP/provider-retirement/validation/lifecycle coverage passed 561/573, with only 12 documented read-only operator-path failures. The new test proves child-exit concurrent with a stall scan has exactly one delivery owner and acknowledgement; auditor large output remains under 65KB until release, while provider handoff expiry reports the precise timeout. Current git diff --check is clean and the pushed branch is clean/up to date. Re-running make test, terminal scan, and secret scan is blocked before execution by the native validation guard chmod failure on its read-only service lock directory; no guard bypass was used.
---
author: oompah
created: 2026-08-06 00:23
---
Completion: delivered and pushed c8e6efcd2 on OOMPAH-833. The standalone main backport retains command liveness through bounded provider delivery for both implementation workers and terminal auditors, reports precise delivery stalls, and has exact-once race coverage. Submitting this exact head for integration and its configured terminal gate.
---
author: oompah
created: 2026-08-06 00:23
---
Ported the reviewed durable ACP command-result delivery repair onto main with bounded handoff, exact-once retirement, observability, and worker/auditor race coverage.
---
author: oompah
created: 2026-08-06 00:23
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 0, Tool calls: 36
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 38s
- Log: OOMPAH-833__20260806T001857Z.jsonl
---
author: oompah
created: 2026-08-06 01:51
---
Branch quality gate passed for `c8e6efcd265bb3cb18ae46213b0adbcbb3e088c1` using `make test` in 660.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-06 02:01
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-06 02:01
---
YOLO: merged PR #727.
---
author: oompah
created: 2026-08-06 02:02
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-06 02:02
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-06 02:06
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: c8e6efcd265bb3cb18ae46213b0adbcbb3e088c1
- main_merge_commit: fd57e2e814c0f944fa7aeb082fd103371561b8ba
- changed_files_count: 7
- changed_paths: oompah/acp_agent.py, oompah/acp_tools.py, oompah/api_agent.py, oompah/orchestrator.py, oompah/tool_liveness.py, tests/test_acp_tool_output_bounds.py, tests/test_tool_liveness.py
- systemic_epic_paths_touched: 0
- new_regression_tests: test_exited_child_enters_result_pending_until_provider_acknowledges; test_child_exit_concurrent_with_stall_scan_has_one_delivery_owner; test_result_delivery_deadline_is_precise_and_recoverable; test_public_state_exposes_pending_liveness_without_provider_details; test_command_result_stays_owned_until_bounded_api_bridge_ack; test_failing_command_uses_the_same_exactly_once_delivery_path; test_large_auditor_result_is_bounded_before_delivery_and_then_released
- branch_gate_result: passed (make test, 660.3s at c8e6efcd2)
- ancestor_of_origin_main: true
- author: oompah <lesserevil@users.noreply.github.com>
---
<!-- COMMENTS:END -->
