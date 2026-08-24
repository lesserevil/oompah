---
id: OOMPAH-1328
type: task
status: In Validation
priority: null
title: Apply large stream limit to OpenCode ACP subprocesses
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T00:59:00.469186Z'
updated_at: '2026-08-24T01:22:17.719559Z'
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
oompah.lifecycle_revision: 3
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
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b4728feba5a7
    project_id: proj-14849f1b
    task_id: OOMPAH-1328
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
    attempts:
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
    updated_at: '2026-08-24T01:21:59.951417+00:00'
  - version: 1
    audit_id: audit-6a7e254a8bb2
    project_id: proj-14849f1b
    task_id: OOMPAH-1328
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5afe5472112b1cac4d9f3a323071e2001dbe0dc88643adb31af26fb6f164963a
    attempts: []
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
<!-- COMMENTS:END -->
