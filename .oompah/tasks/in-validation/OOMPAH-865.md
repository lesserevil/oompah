---
id: OOMPAH-865
type: bug
status: In Validation
priority: null
title: Reserve an independent auditor candidate across contributor retry rotation
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T19:09:44.116383Z'
updated_at: '2026-08-07T10:08:05.576156Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-865
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b4dc339f6dba0ade744e546e15885f0eab90407a123aa5eed4782a0efb82241e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T19:12:40.149364+00:00'
  matched_identifiers: []
  evidence: 'Project-owner review: this is a new regression from OOMPAH-858 contributor
    retry rotation exhausting every configured auditor candidate; no existing active
    task covers reserving an independent terminal auditor across contributor escalation.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-06T19:12:40.149364+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: 'Project-owner review: this is a new regression from OOMPAH-858
    contributor retry rotation exhausting every configured auditor candidate; no existing
    active task covers reserving an independent terminal auditor across contributor
    escalation.'
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-865
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-763--task-OOMPAH-865
  base_branch: epic-OOMPAH-763
  base_sha: a5d1973d043ff2375d56d89d0ea8bd5326e24f63
  head_sha: 04fa6781091efc6f11b952b9f1b35123facce64f
  integrated_sha: 04fa6781091efc6f11b952b9f1b35123facce64f
  submitted_at: '2026-08-07T08:33:01.647721+00:00'
  updated_at: '2026-08-07T09:03:04.494820+00:00'
oompah.task_costs:
  total_input_tokens: 46148
  total_output_tokens: 849
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 45981
      output_tokens: 237
      cost_usd: 0.0
    unknown:
      input_tokens: 167
      output_tokens: 612
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 45981
    output_tokens: 237
    cost_usd: 0.0
    recorded_at: '2026-08-06T19:11:08.155170+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 110
    output_tokens: 21
    cost_usd: 0.0
    recorded_at: '2026-08-07T09:29:35.082505+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 42
    output_tokens: 479
    cost_usd: 0.0
    recorded_at: '2026-08-07T09:48:25.550806+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 15
    output_tokens: 112
    cost_usd: 0.0
    recorded_at: '2026-08-07T10:08:00.964874+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-865__20260806T191048Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-865
    source_sha: 03563661c1b8998cfe5d081edddbe7313b62d10c
    completed_at: '2026-08-06T19:11:08.170498+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-690fb40503ee
    project_id: proj-14849f1b
    task_id: OOMPAH-865
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8405317f59886583c342a88864467740b040e241c2f740913c236a8543ac255a
    attempts:
    - version: 1
      attempt_id: attempt-ef1dae62d434
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8405317f59886583c342a88864467740b040e241c2f740913c236a8543ac255a
      created_at: '2026-08-07T09:15:27.800078+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-07T09:15:27.800078+00:00'
      branch_key: epic-OOMPAH-763--task-OOMPAH-865
      selected_ref: 04fa6781091efc6f11b952b9f1b35123facce64f
      selected_sha: 04fa6781091efc6f11b952b9f1b35123facce64f
      ended_at: '2026-08-07T09:31:10.864061+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-b7f7606cd7e3
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8405317f59886583c342a88864467740b040e241c2f740913c236a8543ac255a
      created_at: '2026-08-07T09:31:19.448292+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-07T09:31:19.448292+00:00'
      branch_key: epic-OOMPAH-763--task-OOMPAH-865
      selected_ref: 04fa6781091efc6f11b952b9f1b35123facce64f
      selected_sha: 04fa6781091efc6f11b952b9f1b35123facce64f
      candidate_rotation_count: 1
      ended_at: '2026-08-07T09:50:50.987123+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-7c783135bb6a
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8405317f59886583c342a88864467740b040e241c2f740913c236a8543ac255a
      created_at: '2026-08-07T09:51:09.002638+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-07T09:51:09.002638+00:00'
      branch_key: epic-OOMPAH-763--task-OOMPAH-865
      selected_ref: 04fa6781091efc6f11b952b9f1b35123facce64f
      selected_sha: 04fa6781091efc6f11b952b9f1b35123facce64f
      candidate_rotation_count: 2
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-07T09:03:33.098057+00:00'
    selected_ref: 04fa6781091efc6f11b952b9f1b35123facce64f
    selected_sha: 04fa6781091efc6f11b952b9f1b35123facce64f
    updated_at: '2026-08-07T09:51:09.002638+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ef1dae62d434
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8405317f59886583c342a88864467740b040e241c2f740913c236a8543ac255a
    created_at: '2026-08-07T09:15:27.800078+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-07T09:15:27.800078+00:00'
    branch_key: epic-OOMPAH-763--task-OOMPAH-865
    selected_ref: 04fa6781091efc6f11b952b9f1b35123facce64f
    selected_sha: 04fa6781091efc6f11b952b9f1b35123facce64f
    ended_at: '2026-08-07T09:31:10.864061+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-b7f7606cd7e3
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8405317f59886583c342a88864467740b040e241c2f740913c236a8543ac255a
    created_at: '2026-08-07T09:31:19.448292+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-07T09:31:19.448292+00:00'
    branch_key: epic-OOMPAH-763--task-OOMPAH-865
    selected_ref: 04fa6781091efc6f11b952b9f1b35123facce64f
    selected_sha: 04fa6781091efc6f11b952b9f1b35123facce64f
    candidate_rotation_count: 1
    ended_at: '2026-08-07T09:50:50.987123+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-7c783135bb6a
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8405317f59886583c342a88864467740b040e241c2f740913c236a8543ac255a
    created_at: '2026-08-07T09:51:09.002638+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-07T09:51:09.002638+00:00'
    branch_key: epic-OOMPAH-763--task-OOMPAH-865
    selected_ref: 04fa6781091efc6f11b952b9f1b35123facce64f
    selected_sha: 04fa6781091efc6f11b952b9f1b35123facce64f
    candidate_rotation_count: 2
---
## Summary

Triggered by OOMPAH-858 after its exact full gate passed and integrated: implementation retries consumed every configured provider/model candidate (Claude haiku, sonnet, opus and Codex terra), leaving the terminal auditor selector with 'All candidates are used by contributors' and forcing Needs Human despite healthy transports. Implementation scope: make contributor candidate selection and retry escalation reserve at least one healthy auditor-role provider/model that remains independent for terminal validation, or deterministically select a contributor/auditor allocation that cannot exhaust the independence set. Cover initial dispatch, stalled-agent escalation, provider rotation, continuation/recovery, configured one-candidate impossibility, and dynamic health/config changes. Preserve provider diversity, explicit owner override semantics, contributor identity evidence, and fail-closed auditing. Relevant code: oompah/auditor_candidate_selector.py, orchestrator contributor/provider selection and retry escalation, configuration validation/health observability, terminal transition recovery. Required tests: reproduce OOMPAH-858's multi-provider retry sequence; prove a reserved independent candidate remains dispatchable; prove impossible configurations surface a pre-dispatch actionable configuration alert instead of consuming all candidates and failing only after integration; prove restart and concurrent task dispatch retain reservation correctness. Acceptance: when configuration has at least two eligible independent candidates, no task can consume the final auditor candidate through contributor retries; exact integrated work reaches an independent audit without operator intervention.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 19:10
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 19:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 19:11
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.0K in / 237 out [46.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 48s
- Log: OOMPAH-865__20260806T191048Z.jsonl
---
author: oompah
created: 2026-08-06 19:11
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861, OOMPAH-862, OOMPAH-863, OOMPAH-864. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
author: oompah
created: 2026-08-07 05:44
---
Implementation committed and pushed at 3e03359da9baed0a36b34dd9a301ad921f2cee96 on epic-OOMPAH-763--task-OOMPAH-865. Pre-rebase frozen patch passed 998 tests serial and 998 parallel; final focus-triage transport races passed directly and independent review accepted. Rebase onto current origin/epic-OOMPAH-763 completed without conflicts and preserved both incoming O856/O858 callbacks plus O865 budget/authority callbacks. A narrow post-rebase overlap gate remains before task submit.
---
author: oompah
created: 2026-08-07 05:56
---
Reserve the final independent auditor across contributor retries with durable provider/model health, budget, contributor evidence, and exact transport-edge authority. Pre-rebase gate: 998 serial + 998 parallel; post-rebase overlap gate: 32 serial + 32 parallel; independent post-rebase review accepted exact head 3e03359da.
---
author: oompah
created: 2026-08-07 06:26
---
The combined-tree quality gate failed on `epic-OOMPAH-763--task-OOMPAH-865`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
thon3.12/site-packages/_pytest/tracemalloc.py:9: RuntimeWarning: coroutine 'LogFileWatcher.start' was never awaited
    import tracemalloc
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_http_auth.py::TestVerifyPassword::test_invalid_hash_format
tests/test_http_auth.py::TestVerifyPassword::test_valid_bcrypt_password
tests/test_http_auth.py::TestVerifyPassword::test_wrong_bcrypt_password
tests/test_http_auth.py::TestLoadCredentials::test_absolute_path_override_used_as_is
  /home/shedwards/.oompah/tmp/oompah-quality-gate-h4xhw6vu/workspace/.venv/lib/python3.12/site-packages/passlib/utils/__init__.py:854: DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13
    from crypt import crypt as _crypt

tests/test_http_auth.py: 21 warnings
  /home/shedwards/.oompah/tmp/oompah-quality-gate-h4xhw6vu/workspace/tests/test_http_auth.py:37: DeprecationWarning: the method passlib.context.CryptContext.encrypt() is deprecated as of Passlib 1.7, and will be removed in Passlib 2.0, use CryptContext.hash() instead.
    return ctx.encrypt("password")

tests/test_http_auth.py::TestVerifyPassword::test_valid_apr1_password
tests/test_http_auth.py::TestVerifyPassword::test_wrong_apr1_password
tests/test_http_auth.py::TestLoadHtpasswdFile::test_valid_multiple_entries
tests/test_http_auth.py::TestVerifierCallable::test_multiple_users
  /home/shedwards/.oompah/tmp/oompah-quality-gate-h4xhw6vu/workspace/tests/test_http_auth.py:49: DeprecationWarning: the method passlib.context.CryptContext.encrypt() is deprecated as of Passlib 1.7, and will be removed in Passlib 2.0, use CryptContext.hash() instead.
    return ctx.encrypt("password")

tests/test_mcp_gateway.py::test_mcp_client_can_initialize_list_allowed_tools_and_call_state
tests/test_mcp_gateway.py::test_authenticated_mcp_client_can_initialize_list_and_call_protected_api
  /home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/contextlib.py:105: DeprecationWarning: Use `streamable_http_client` instead.
    self.gen = func(*args, **kwds)

tests/test_sdk_install_guards.py::TestClaudeSessionMcpServerGuard::test_no_tool_catalog_skips_mcp_server_path
  /home/shedwards/.oompah/tmp/oompah-quality-gate-h4xhw6vu/workspace/oompah/acp_backends/claude.py:521: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    async for msg in client.receive_response():
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_server_release_picks.py::TestPatchReleasePicksEndpoint::test_returns_400_on_invalid_json
tests/test_server_release_picks.py::TestPostApplyReleasePicksToAllChildren::test_returns_400_on_invalid_json
  /home/shedwards/.oompah/tmp/oompah-quality-gate-h4xhw6vu/workspace/.venv/lib/python3.12/site-packages/httpx/_models.py:408: DeprecationWarning: Use 'content=<...>' to upload raw bytes/text content.
    headers, stream = encode_request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_event_driven_loop.py::TestRunEventDrivenLoop::test_run_calls_tick_for_queued_events
FAILED tests/test_focus.py::TestDuplicateDetectorFocus::test_async_triage_excludes_structurally_completed_duplicate_focus
FAILED tests/test_terminal_audit_workspace_recovery.py::test_genuine_candidate_exhaustion_remains_no_auditor
FAILED tests/test_terminal_audit_workspace_recovery.py::test_unsafe_metadata_archive_is_not_recorded_as_transport_failure
FAILED tests/test_terminal_audit_workspace_recovery.py::test_workspace_failure_exhaustion_is_not_reported_as_no_auditor
= 5 failed, 16406 passed, 8 skipped, 1 xfailed, 37 warnings in 1066.35s (0:17:46) =

make: *** [Makefile:401: test] Error 1

```
---
author: oompah
created: 2026-08-07 08:32
---
Post-OOMPAH-867 restart submission: server and canonical CLI are healthy at c22debc4e. Repaired exact branch head 04fa6781091efc6f11b952b9f1b35123facce64f is clean, pushed, independently accepted, and passed its modified-module canonical leased validation (211 serial and 211 xdist4) plus the five original gate failures. Submitting now for an uninterrupted exact branch gate.
---
author: oompah
created: 2026-08-07 08:33
---
Stabilized combined-gate event-loop/focus/audit-workspace tests with deterministic synchronization and exact resource-release assertions.
---
author: oompah
created: 2026-08-07 09:03
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-07 09:15
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-07 09:15
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-07 09:29
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 6
- Tokens: 110 in / 21 out [131 total]
- Cost: $0.0000
- Exit: terminated, Duration: 14m 5s
- Log: OOMPAH-865__20260807T091600Z.jsonl
---
author: oompah
created: 2026-08-07 09:31
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-07 09:31
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-07 09:48
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 0, Tool calls: 21
- Tokens: 42 in / 479 out [521 total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 0s
- Log: OOMPAH-865__20260807T093145Z.jsonl
---
author: oompah
created: 2026-08-07 09:51
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-07 09:51
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-07 10:08
---
Run #3 [attempt=3, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 4
- Tokens: 15 in / 112 out [127 total]
- Cost: $0.0000
- Exit: terminated, Duration: 16m 40s
- Log: OOMPAH-865__20260807T095133Z.jsonl
---
<!-- COMMENTS:END -->
