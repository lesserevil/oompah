---
id: OOMPAH-1328
type: task
status: Merged
priority: null
title: Apply large stream limit to OpenCode ACP subprocesses
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T00:59:00.469186Z'
updated_at: '2026-08-24T01:32:57.532327Z'
work_branch: OOMPAH-1328
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 32623887-6658-4507-aebe-1f82fa244df7
  request_fingerprint: 3e72702ee72c5191f330bc2235080b55d6d11adf9beb0ee63295241e50b8ada2
oompah.lifecycle_revision: 4
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1328
  base_branch: main
  base_sha: 859930db3ade55125aafb55fa634c1e49f9e57a4
  head_sha: aaac848e78bef6ee935df3c6697bcaa53012bfbb
  submitted_at: '2026-08-24T01:01:01.865641+00:00'
  updated_at: '2026-08-24T01:01:01.865641+00:00'
oompah.work_branch: OOMPAH-1328
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-b4728feba5a7
    project_id: proj-14849f1b
    task_id: OOMPAH-1328
    digest: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
  - version: 1
    audit_id: audit-6a7e254a8bb2
    project_id: proj-14849f1b
    task_id: OOMPAH-1328
    digest: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1328","audit-b4728feba5a7","attempt-4284efaf83d2"]': '2026-08-24T01:27:06.188688+00:00'
    '["proj-14849f1b","OOMPAH-1328","audit-6a7e254a8bb2","attempt-7de8f3966a2e"]': '2026-08-24T01:32:29.266556+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1328
    target_state: Done
    evidence_fingerprint: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
    workflow_revision: null
    selected_ref: aaac848e78bef6ee935df3c6697bcaa53012bfbb
    selected_sha: aaac848e78bef6ee935df3c6697bcaa53012bfbb
    landing_revision: null
    audit_ids:
    - audit-b4728feba5a7
    kind: result
    applied: true
    retired_at: '2026-08-24T01:27:06.188706+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1328
    target_state: Merged
    evidence_fingerprint: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
    workflow_revision: null
    selected_ref: aaac848e78bef6ee935df3c6697bcaa53012bfbb
    selected_sha: aaac848e78bef6ee935df3c6697bcaa53012bfbb
    landing_revision: null
    audit_ids:
    - audit-6a7e254a8bb2
    kind: result
    applied: true
    retired_at: '2026-08-24T01:32:29.266577+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1328
    audit_id: audit-b4728feba5a7
    attempt_id: attempt-4284efaf83d2
    target_state: Done
    evidence_fingerprint: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
    status: In Validation
    audit_ids:
    - audit-b4728feba5a7
    kind: result
    applied: true
    created_at: '2026-08-24T01:27:06.188717+00:00'
    applied_at: '2026-08-24T01:27:13.425240+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1328
    audit_id: audit-6a7e254a8bb2
    attempt_id: attempt-7de8f3966a2e
    target_state: Merged
    evidence_fingerprint: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
    status: Merged
    audit_ids:
    - audit-6a7e254a8bb2
    kind: result
    applied: true
    created_at: '2026-08-24T01:32:29.266591+00:00'
    applied_at: '2026-08-24T01:32:37.722337+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b4728feba5a7
    project_id: proj-14849f1b
    task_id: OOMPAH-1328
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
    attempts:
    - version: 1
      attempt_id: attempt-4284efaf83d2
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
      created_at: '2026-08-24T01:21:59.951417+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T01:21:59.951417+00:00'
      branch_key: OOMPAH-1328
      selected_ref: aaac848e78bef6ee935df3c6697bcaa53012bfbb
      selected_sha: aaac848e78bef6ee935df3c6697bcaa53012bfbb
      verdict: pass
      completed_at: '2026-08-24T01:27:06.188513+00:00'
      ended_at: '2026-08-24T01:27:06.188513+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-24T01:10:38.663923+00:00'
    eligible_at: '2026-08-24T01:10:38.663923+00:00'
    selected_ref: aaac848e78bef6ee935df3c6697bcaa53012bfbb
    selected_sha: aaac848e78bef6ee935df3c6697bcaa53012bfbb
    updated_at: '2026-08-24T01:27:06.188513+00:00'
  - version: 1
    audit_id: audit-6a7e254a8bb2
    project_id: proj-14849f1b
    task_id: OOMPAH-1328
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
    attempts:
    - version: 1
      attempt_id: attempt-7de8f3966a2e
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
      created_at: '2026-08-24T01:27:34.991167+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T01:27:34.991167+00:00'
      branch_key: OOMPAH-1328
      selected_ref: aaac848e78bef6ee935df3c6697bcaa53012bfbb
      selected_sha: aaac848e78bef6ee935df3c6697bcaa53012bfbb
      verdict: pass
      completed_at: '2026-08-24T01:32:29.266407+00:00'
      ended_at: '2026-08-24T01:32:29.266407+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-24T01:10:38.663923+00:00'
    prerequisite_audit_id: audit-b4728feba5a7
    selected_ref: aaac848e78bef6ee935df3c6697bcaa53012bfbb
    selected_sha: aaac848e78bef6ee935df3c6697bcaa53012bfbb
    updated_at: '2026-08-24T01:32:29.266407+00:00'
    eligible_at: '2026-08-24T01:27:06.188513+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-4284efaf83d2
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
    created_at: '2026-08-24T01:21:59.951417+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T01:21:59.951417+00:00'
    branch_key: OOMPAH-1328
    selected_ref: aaac848e78bef6ee935df3c6697bcaa53012bfbb
    selected_sha: aaac848e78bef6ee935df3c6697bcaa53012bfbb
  - version: 1
    attempt_id: attempt-7de8f3966a2e
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
    created_at: '2026-08-24T01:27:34.991167+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T01:27:34.991167+00:00'
    branch_key: OOMPAH-1328
    selected_ref: aaac848e78bef6ee935df3c6697bcaa53012bfbb
    selected_sha: aaac848e78bef6ee935df3c6697bcaa53012bfbb
oompah.task_costs:
  total_input_tokens: 412
  total_output_tokens: 16266
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 412
      output_tokens: 16266
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 218
    output_tokens: 8968
    cost_usd: 0.0
    recorded_at: '2026-08-24T01:27:25.903898+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 194
    output_tokens: 7298
    cost_usd: 0.0
    recorded_at: '2026-08-24T01:32:53.067071+00:00'
---
## Summary

Completion auditors using the OpenCode ACP backend still fail with ValueError: Separator is found, but chunk is longer than limit after OOMPAH-1327, because oompah/acp_backends/opencode.py invokes asyncio.create_subprocess_exec without limit=MAX_LINE_SIZE. This repeatedly exhausts terminal-audit retries, moves tasks to Needs Human, creates tracker-authority churn, and prevents restart reconstruction from admitting workers, leaving non-terminal tasks inactive. Implement the same bounded 10 MiB subprocess stream limit on the OpenCode backend. Add regression coverage in tests/test_acp_opencode_backend.py asserting the spawn limit and handling an output line larger than 64 KiB. Run focused OpenCode backend tests and the branch gate. Acceptance: OpenCode auditors no longer raise the asyncio separator/limit ValueError; exhausted affected audits can be safely rearmed; workflow reconstruction converges and inactive non-terminal work resumes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 01:00
---
Root cause confirmed in the live server: OpenCode completion auditors bypass AgentSession and create subprocess streams without MAX_LINE_SIZE. Implementing the missing limit with regression coverage.
---
author: oompah
created: 2026-08-24 01:01
---
Fixed OpenCode ACP subprocess stream buffering by applying MAX_LINE_SIZE to asyncio.create_subprocess_exec. Regression test verifies the configured limit; tests/test_acp_opencode_backend.py passes (40 tests).
---
author: oompah
created: 2026-08-24 01:10
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-24 01:22
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-24 01:22
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 01:27
---
Audit PASS — Done

Implementation verified: OpenCode ACP backend now applies 10 MiB stream limit (limit=MAX_LINE_SIZE) to subprocess creation, mirroring agent.py pattern. Regression test added to verify limit is passed to asyncio.create_subprocess_exec. Full gate (make test) passed for exact SHA. Fixes asyncio ValueError from oversized stream chunks affecting completion auditors.

Safe evidence:
- implementation: limit=MAX_LINE_SIZE applied at oompah/acp_backends/opencode.py:443 to asyncio.create_subprocess_exec
- constant: MAX_LINE_SIZE = 10 * 1024 * 1024 bytes (10 MiB) from oompah/agent.py:21
- test: test_run_turn_sets_large_subprocess_stream_limit verifies limit kwarg is passed correctly
- quality_gate: make test passed for SHA aaac848e78bef6ee935df3c6697bcaa53012bfbb in 179.5 seconds
---
author: oompah
created: 2026-08-24 01:27
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 65, Tool calls: 26
- Tokens: 218 in / 9.0K out [9.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 22s
- Log: OOMPAH-1328__20260824T012230Z.jsonl
---
author: oompah
created: 2026-08-24 01:27
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-24 01:27
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 01:32
---
Audit PASS — Merged

Implementation verified: OpenCode ACP backend correctly applies 10 MiB stream limit (limit=MAX_LINE_SIZE) to asyncio.create_subprocess_exec at oompah/acp_backends/opencode.py:436-443. Regression test test_run_turn_sets_large_subprocess_stream_limit verifies the limit parameter is passed correctly. Full gate (make test) passed for exact head SHA in 179.51 seconds. All task acceptance criteria met.

Safe evidence:
- implementation: limit=MAX_LINE_SIZE parameter applied to asyncio.create_subprocess_exec at oompah/acp_backends/opencode.py lines 436-443
- constant: MAX_LINE_SIZE = 10 * 1024 * 1024 bytes (10 MiB) from oompah/agent.py:21
- test_coverage: test_run_turn_sets_large_subprocess_stream_limit in tests/test_acp_opencode_backend.py mocks asyncio.create_subprocess_exec and verifies limit kwarg equals MAX_LINE_SIZE
- quality_gate: make test passed for SHA aaac848e78bef6ee935df3c6697bcaa53012bfbb in 179.51 seconds
---
author: oompah
created: 2026-08-24 01:32
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 52, Tool calls: 23
- Tokens: 194 in / 7.3K out [7.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 11s
- Log: OOMPAH-1328__20260824T012756Z.jsonl
---
<!-- COMMENTS:END -->
