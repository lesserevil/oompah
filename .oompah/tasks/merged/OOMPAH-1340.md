---
id: OOMPAH-1340
type: bug
status: Merged
priority: null
title: Task submit rejects generated helper paths that were deleted from the submitted
  head
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-25T18:29:09.896071Z'
updated_at: '2026-08-25T19:43:40.259688Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 76403418-a933-4a65-a346-6e8e21f133c9
  request_fingerprint: 9cd737f3213b89d8a30fdb8825ab80b5f1344d939508805d2bb80cfd00b3a109
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-a08fa7910e1a
    project_id: proj-14849f1b
    task_id: OOMPAH-1340
    digest: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
  - version: 1
    audit_id: audit-a9d23f4f58f2
    project_id: proj-14849f1b
    task_id: OOMPAH-1340
    digest: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1340","audit-a08fa7910e1a","attempt-b18460037370"]': '2026-08-25T19:20:25.604041+00:00'
    '["proj-14849f1b","OOMPAH-1340","audit-a9d23f4f58f2","attempt-21c8f20800b1"]': '2026-08-25T19:43:06.569469+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1340
    target_state: Done
    evidence_fingerprint: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
    workflow_revision: null
    selected_ref: origin/OOMPAH-1340
    selected_sha: c4d9c48eba5a2dfc282596debb2b5843ab50919b
    landing_revision: null
    audit_ids:
    - audit-a08fa7910e1a
    kind: result
    applied: true
    retired_at: '2026-08-25T19:20:25.604057+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1340
    target_state: Merged
    evidence_fingerprint: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
    workflow_revision: null
    selected_ref: origin/OOMPAH-1340
    selected_sha: c4d9c48eba5a2dfc282596debb2b5843ab50919b
    landing_revision: null
    audit_ids:
    - audit-a9d23f4f58f2
    kind: result
    applied: true
    retired_at: '2026-08-25T19:43:06.569489+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1340
    audit_id: audit-a08fa7910e1a
    attempt_id: attempt-b18460037370
    target_state: Done
    evidence_fingerprint: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
    status: In Validation
    audit_ids:
    - audit-a08fa7910e1a
    kind: result
    applied: true
    created_at: '2026-08-25T19:20:25.604068+00:00'
    applied_at: '2026-08-25T19:20:33.036590+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1340
    audit_id: audit-a9d23f4f58f2
    attempt_id: attempt-21c8f20800b1
    target_state: Merged
    evidence_fingerprint: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
    status: Merged
    audit_ids:
    - audit-a9d23f4f58f2
    kind: result
    applied: true
    created_at: '2026-08-25T19:43:06.569503+00:00'
    applied_at: '2026-08-25T19:43:17.017593+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a08fa7910e1a
    project_id: proj-14849f1b
    task_id: OOMPAH-1340
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
    attempts:
    - version: 1
      attempt_id: attempt-b18460037370
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
      created_at: '2026-08-25T19:00:48.699363+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-25T19:00:48.699363+00:00'
      branch_key: OOMPAH-1340
      selected_ref: origin/OOMPAH-1340
      selected_sha: c4d9c48eba5a2dfc282596debb2b5843ab50919b
      verdict: pass
      completed_at: '2026-08-25T19:20:25.603837+00:00'
      ended_at: '2026-08-25T19:20:25.603837+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-25T18:45:13.020693+00:00'
    eligible_at: '2026-08-25T18:45:13.020693+00:00'
    selected_ref: origin/OOMPAH-1340
    selected_sha: c4d9c48eba5a2dfc282596debb2b5843ab50919b
    updated_at: '2026-08-25T19:20:25.603837+00:00'
  - version: 1
    audit_id: audit-a9d23f4f58f2
    project_id: proj-14849f1b
    task_id: OOMPAH-1340
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
    attempts:
    - version: 1
      attempt_id: attempt-21c8f20800b1
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
      created_at: '2026-08-25T19:20:59.743380+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-25T19:20:59.743380+00:00'
      branch_key: OOMPAH-1340
      selected_ref: origin/OOMPAH-1340
      selected_sha: c4d9c48eba5a2dfc282596debb2b5843ab50919b
      verdict: pass
      completed_at: '2026-08-25T19:43:06.569295+00:00'
      ended_at: '2026-08-25T19:43:06.569295+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-25T18:45:13.020693+00:00'
    prerequisite_audit_id: audit-a08fa7910e1a
    selected_ref: origin/OOMPAH-1340
    selected_sha: c4d9c48eba5a2dfc282596debb2b5843ab50919b
    updated_at: '2026-08-25T19:43:06.569295+00:00'
    eligible_at: '2026-08-25T19:20:25.603837+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-b18460037370
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
    created_at: '2026-08-25T19:00:48.699363+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-25T19:00:48.699363+00:00'
    branch_key: OOMPAH-1340
    selected_ref: origin/OOMPAH-1340
    selected_sha: c4d9c48eba5a2dfc282596debb2b5843ab50919b
  - version: 1
    attempt_id: attempt-21c8f20800b1
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
    created_at: '2026-08-25T19:20:59.743380+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-25T19:20:59.743380+00:00'
    branch_key: OOMPAH-1340
    selected_ref: origin/OOMPAH-1340
    selected_sha: c4d9c48eba5a2dfc282596debb2b5843ab50919b
oompah.lifecycle_revision: 2
oompah.task_costs:
  total_input_tokens: 724
  total_output_tokens: 20704
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 724
      output_tokens: 20704
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 450
    output_tokens: 12760
    cost_usd: 0.0
    recorded_at: '2026-08-25T19:20:53.793391+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 274
    output_tokens: 7944
    cost_usd: 0.0
    recorded_at: '2026-08-25T19:43:33.771371+00:00'
---
## Summary

### Problem
`oompah task submit` rejects a repaired task branch when an Oompah-generated helper was removed in the repair commit. Reproduced on TRICKLE-142: `.oompah-no-hooks/prepare-commit-msg` is absent from HEAD and the remote head, but submission still says it is present.

### Root cause
`task_cli._git_submission_evidence()` computes `changed_paths` with `git diff --name-only <merge-base>..HEAD`, which includes deleted paths. `server._submission_record()` rejects any changed path matching `is_generated_worktree_helper`, without distinguishing a file present in the submitted tree from a deletion. Therefore the required repair (`git rm`, commit, push) can never satisfy submission: the deletion itself remains in changed_paths and is rejected.

### Scope
Change submission evidence or server validation so only generated helper paths present in the submitted HEAD are rejected. Prefer emitting changed paths with a diff filter excluding deletions, while preserving all added/modified/renamed/copied paths used by submission fencing. Add defense-in-depth server validation if needed.

### Tests
- A branch adding/tracking `.oompah-no-hooks/prepare-commit-msg` is rejected.
- A branch deleting the helper from its base is accepted.
- Ordinary deleted source files do not corrupt changed-path evidence.

### Acceptance Criteria
- TRICKLE-142 clean head 2ee10c54b (helper absent from HEAD) can be submitted.
- Generated helpers present in HEAD remain rejected.
- Submission authority tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-25 18:45
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-25 19:00
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-25 19:01
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-25 19:20
---
Audit PASS — Done

OOMPAH-1340 fix is complete and correct. Changed `_git_submission_evidence()` to exclude deleted paths from submission evidence using `--diff-filter=ACMRTUXB`. Comprehensive testing confirms: (1) deleted helpers no longer block submission, (2) generated helpers present in HEAD remain rejected by server validation, (3) regression test verifies the fix behavior end-to-end. All 345 targeted tests pass including server-side validation test that confirms generated helpers are still rejected when present.

Safe evidence:
- test_results.regression_test: test_submission_evidence_excludes_deleted_paths PASSED - verifies deleted helpers excluded from changed_paths
- test_results.server_validation_test: test_submit_endpoint_rejects_generated_worktree_helper_evidence PASSED - confirms server still rejects generated helpers
- test_results.task_cli_tests: 158 passed
- test_results.unpushed_gate_tests: 30 passed
- test_results.worker_submission_tests: 29 passed
- test_results.targeted_tests: 345 passed (helpers/submission/changed_path related)
- code_changes.file: oompah/task_cli.py
- code_changes.change: Added --diff-filter=ACMRTUXB to git diff command to exclude deleted paths (D) from changed_paths
- code_changes.diff_filter_explanation: ACMRTUXB includes: Added, Copied, Modified, Renamed, Type-changed, Unmerged, paired changes; excludes Deleted
- acceptance_criteria.deleted_helpers_accepted: true - regression test confirms deletion no longer blocks submission
- acceptance_criteria.added_helpers_rejected: true - server validation test confirms rejection when present
- acceptance_criteria.deleted_files_not_corrupted: true - diff filter ensures only real changes included
---
author: oompah
created: 2026-08-25 19:20
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 117, Tool calls: 55
- Tokens: 450 in / 12.8K out [13.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 20m 1s
- Log: OOMPAH-1340__20260825T190118Z.jsonl
---
author: oompah
created: 2026-08-25 19:21
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-25 19:21
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-25 19:43
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- code_changes.file: oompah/task_cli.py
- code_changes.change: Added --diff-filter=ACMRTUXB to git diff command in _git_submission_evidence function
- code_changes.filter_explanation: Excludes deleted paths (D) while preserving A=Added, C=Copied, M=Modified, R=Renamed, T=Type-changed, U=Unmerged, X=Unknown, B=Paired changes
- test_evidence.regression_test: test_submission_evidence_excludes_deleted_paths PASSED
- test_evidence.server_validation_test: test_submit_endpoint_rejects_generated_worktree_helper_evidence PASSED
- test_evidence.task_cli_tests: 158 passed
- test_evidence.worker_submission_tests: 29 passed
- test_evidence.submission_fencing_tests: 20 passed
- test_evidence.total_critical_tests: 207 passed
- acceptance_criteria.deleted_helpers_excluded: true - regression test confirms deletion no longer blocks submission
- acceptance_criteria.generated_helpers_present_rejected: true - server validation test confirms rejection when present
- acceptance_criteria.deleted_files_not_corrupted: true - diff filter ensures only real changes included
- regression_test_coverage: End-to-end test with real git repo, helper file deletion, source file addition
- test_command: python -m pytest tests/test_task_cli.py tests/test_worker_submission.py tests/test_submission_fencing.py
- test_result: 207 passed in 16.24s
- head_sha: c4d9c48eba5a2dfc282596debb2b5843ab50919b
---
author: oompah
created: 2026-08-25 19:43
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 74, Tool calls: 33
- Tokens: 274 in / 7.9K out [8.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 22m 24s
- Log: OOMPAH-1340__20260825T192131Z.jsonl
---
<!-- COMMENTS:END -->
