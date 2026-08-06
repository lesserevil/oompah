---
id: OOMPAH-612
type: bug
status: In Validation
priority: 1
title: Avoid ACP auditor result deadlock on the dispatch event loop
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T19:33:15.081209Z'
updated_at: '2026-08-06T20:44:02.672908Z'
work_branch: OOMPAH-612
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/595
review_number: '595'
merged_at: null
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: OOMPAH-612
  head_sha: 8ce6fa0ad3a343b053298a64f721a6a3b73ceb22
  submitted_at: '2026-07-30T19:43:50.264292+00:00'
  updated_at: '2026-07-30T19:43:50.264292+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/595
oompah.review_number: '595'
oompah.work_branch: OOMPAH-612
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-9b5e2b06fe84: '2026-07-30T19:55:52.677971+00:00'
    attempt-f25bce183791: '2026-07-30T20:00:03.597889+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f361fb3dd5c8
    project_id: proj-14849f1b
    task_id: OOMPAH-612
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 367b643b0dc201fcb00b364e5dc51b3683d583e00500e1adc5dd32e0749d2628
    attempts:
    - version: 1
      attempt_id: attempt-9b5e2b06fe84
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 367b643b0dc201fcb00b364e5dc51b3683d583e00500e1adc5dd32e0749d2628
      created_at: '2026-07-30T19:53:23.492952+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T19:53:23.492952+00:00'
      branch_key: OOMPAH-612
      verdict: pass
      completed_at: '2026-07-30T19:55:52.677774+00:00'
      ended_at: '2026-07-30T19:55:52.677774+00:00'
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T19:50:48.280429+00:00'
    updated_at: '2026-07-30T19:55:52.677774+00:00'
  - version: 1
    audit_id: audit-f49ea3036489
    project_id: proj-14849f1b
    task_id: OOMPAH-612
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 367b643b0dc201fcb00b364e5dc51b3683d583e00500e1adc5dd32e0749d2628
    attempts:
    - version: 1
      attempt_id: attempt-f25bce183791
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 367b643b0dc201fcb00b364e5dc51b3683d583e00500e1adc5dd32e0749d2628
      created_at: '2026-07-30T19:56:07.467799+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T19:56:07.467799+00:00'
      branch_key: OOMPAH-612
      verdict: pass
      completed_at: '2026-07-30T20:00:03.597707+00:00'
      ended_at: '2026-07-30T20:00:03.597707+00:00'
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T19:50:48.280429+00:00'
    updated_at: '2026-07-30T20:00:03.597707+00:00'
  - version: 1
    audit_id: audit-7d91f741b0a4
    project_id: proj-14849f1b
    task_id: OOMPAH-612
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e06569fbedf6229d2cdca89efb81bc9d4fa18efa46883f56ed18b7827e86db31
    attempts:
    - version: 1
      attempt_id: attempt-1a433b4ee5fd
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e06569fbedf6229d2cdca89efb81bc9d4fa18efa46883f56ed18b7827e86db31
      created_at: '2026-08-06T20:43:50.756102+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-06T20:43:50.756102+00:00'
      branch_key: OOMPAH-612
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-06T20:42:28.733347+00:00'
    updated_at: '2026-08-06T20:43:50.756102+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-9b5e2b06fe84
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 367b643b0dc201fcb00b364e5dc51b3683d583e00500e1adc5dd32e0749d2628
    created_at: '2026-07-30T19:53:23.492952+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T19:53:23.492952+00:00'
    branch_key: OOMPAH-612
  - version: 1
    attempt_id: attempt-f25bce183791
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 367b643b0dc201fcb00b364e5dc51b3683d583e00500e1adc5dd32e0749d2628
    created_at: '2026-07-30T19:56:07.467799+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T19:56:07.467799+00:00'
    branch_key: OOMPAH-612
  - version: 1
    attempt_id: attempt-1a433b4ee5fd
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e06569fbedf6229d2cdca89efb81bc9d4fa18efa46883f56ed18b7827e86db31
    created_at: '2026-08-06T20:43:50.756102+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-06T20:43:50.756102+00:00'
    branch_key: OOMPAH-612
oompah.task_costs:
  total_input_tokens: 109
  total_output_tokens: 17434
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 109
      output_tokens: 17434
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 44
    output_tokens: 6990
    cost_usd: 0.0
    recorded_at: '2026-07-30T19:56:02.157151+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 65
    output_tokens: 10444
    cost_usd: 0.0
    recorded_at: '2026-07-30T20:00:15.639176+00:00'
---
## Summary

Triggered by: OOMPAH-610

Implementation scope: Fix the ACP Completion Auditor submit_audit_result bridge in oompah/orchestrator.py and oompah/acp_tools.py. The ACP SDK tool is async and invokes the synchronous audit_result_handler on the dispatch event-loop thread; the current handler calls asyncio.run_coroutine_threadsafe(..., same_loop).result(timeout=60), blocking that loop for 60 seconds. The coordinator result is then applied only after the timeout returns an error, causing a valid PASS to be persisted while the auditor is told it was rejected and retries indefinitely. Preserve the API-agent thread-pool bridge, but give ACP an awaitable path (or explicitly offload its synchronous handler) so the coordinator completes once and the tool returns its actual accepted/idempotent outcome without blocking the loop. Include bounded error handling and preserve target/attempt validation.\n\nRequired tests: Add a regression that executes the ACP submit_audit_result async tool on the same running event loop and proves the handler/coordinator completes without timeout or retry, returns accepted=true, and does not double-apply an idempotent attempt. Retain API-agent result-handler coverage and add a failure-path assertion. Run focused auditor/ACP/terminal-transition tests and make test.\n\nAcceptance criteria: ACP auditor PASS/FAIL submissions return the coordinator outcome promptly; a successful durable result is never reported as 'audit scheduler rejected result' merely because the dispatch loop was blocked; the auditor exits normally after one successful submission; graceful draining cannot be held indefinitely by this loop; all relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 19:35
---
Claimed by the interactive operator session. Keeping the task non-dispatchable while repairing the ACP submit bridge because the running service cannot safely self-audit this event-loop defect without reproducing the 60-second loop block. Root cause was live-reproduced by OOMPAH-610 audit attempt attempt-9ad0fa99a03f.
---
author: oompah
created: 2026-07-30 19:43
---
Implemented the ACP bridge repair: Claude and OpenCode async submit_audit_result tools now offload the synchronous run_coroutine_threadsafe coordinator bridge, keeping the dispatch loop free to apply and return the actual result. Added same-loop success/idempotency regressions for both async ACP catalogs and a coordinator-rejection regression. Focused suite: 237 passed. Full make test: 13,729 passed, 7 skipped; terminal mutation scan and secret scan passed.
---
author: oompah
created: 2026-07-30 19:43
---
Offload Claude/OpenCode ACP audit-result submission bridges so the event loop can apply the coordinator result; add same-loop success, idempotency, and rejection regressions. Full make test passed 13,729 with 7 skipped.
---
author: oompah
created: 2026-07-30 19:50
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 19:53
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 19:53
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 19:55
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: 8ce6fa0ad3a343b053298a64f721a6a3b73ceb22
- merge_commit: c048ba706cbe9b1342b80a67576a49b82887e84a
- changed_files: oompah/acp_tools.py, tests/test_acp_auditor_result_bridge.py
- fix_locations: oompah/acp_tools.py:1241 (Claude ACP), oompah/acp_tools.py:1857 (OpenCode ACP)
- fix_mechanism: await asyncio.to_thread(submit_auditor_result, payload, audit_target, audit_result_handler)
- regression_tests: tests/test_acp_auditor_result_bridge.py::test_claude_acp_submission_does_not_block_its_dispatch_loop, tests/test_acp_auditor_result_bridge.py::test_opencode_acp_submission_does_not_block_its_dispatch_loop, tests/test_acp_auditor_result_bridge.py::test_claude_acp_submission_surfaces_coordinator_rejection
- focused_suite_result: 187 passed (test_auditor_contract + test_auditor_result_api + test_terminal_transition_coordinator + test_acp_auditor_result_bridge)
- worktree_status: clean; up to date with origin/main
---
author: oompah
created: 2026-07-30 19:56
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 45, Tool calls: 38
- Tokens: 44 in / 7.0K out [7.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 38s
- Log: OOMPAH-612__20260730T195327Z.jsonl
---
author: oompah
created: 2026-07-30 19:56
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 19:56
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 19:59
---
Live deployment evidence for the pending Merged audit: service instance c1f4a4cb-217d-4c2a-aad6-f768a3cdbb4b is running merge c048ba706. The preceding Claude ACP Done auditor called submit_audit_result at 19:55:52.666 and received accepted=true at 19:55:54.810 (2.14s), then exited normally; no 60-second rejection or retry occurred. PR #595 CI passed on Python 3.11, 3.12, and 3.13. Please submit the structured Merged verdict after completing read-only review.
---
author: oompah
created: 2026-07-30 20:00
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- branch_head: c048ba706cbe9b1342b80a67576a49b82887e84a
- fix_commit: 8ce6fa0ad3a343b053298a64f721a6a3b73ceb22
- merge_parents: e1e4e0c9fee2a17b5a9b02002fcaa2d3cc7793ec 8ce6fa0ad3a343b053298a64f721a6a3b73ceb22
- changed_files: oompah/acp_tools.py, tests/test_acp_auditor_result_bridge.py
- fix_locations: oompah/acp_tools.py:1241 (Claude ACP), oompah/acp_tools.py:1857 (OpenCode ACP)
- fix_mechanism: await asyncio.to_thread(submit_auditor_result, payload, audit_target, audit_result_handler)
- regression_tests: tests/test_acp_auditor_result_bridge.py::test_claude_acp_submission_does_not_block_its_dispatch_loop, ::test_opencode_acp_submission_does_not_block_its_dispatch_loop, ::test_claude_acp_submission_surfaces_coordinator_rejection
- focused_suite_result: 187 passed (test_auditor_contract=13, test_auditor_result_api=68, test_terminal_transition_coordinator=103, test_acp_auditor_result_bridge=3)
- worktree_status: clean; OOMPAH-612 tracks origin/main
---
author: oompah
created: 2026-07-30 20:00
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 71, Tool calls: 59
- Tokens: 65 in / 10.4K out [10.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 7s
- Log: OOMPAH-612__20260730T195612Z.jsonl
---
author: oompah
created: 2026-08-06 20:43
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-06 20:44
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
