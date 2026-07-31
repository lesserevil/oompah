---
id: OOMPAH-437
type: task
status: Archived
priority: null
title: Promote YOLO decomposition children after application
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T02:42:07.784157Z'
updated_at: '2026-07-31T03:19:25.422985Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9881b9c6-409b-411b-8c5d-a2876ff4b3cb
oompah.task_costs:
  total_input_tokens: 59
  total_output_tokens: 8658
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 59
      output_tokens: 8658
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 11
    output_tokens: 40
    cost_usd: 0.0
    recorded_at: '2026-07-24T02:44:54.701520+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 48
    output_tokens: 8618
    cost_usd: 0.0
    recorded_at: '2026-07-31T03:19:23.705477+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-b2bec492ab17: '2026-07-31T03:19:09.722896+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a64e188caf1b
    project_id: proj-14849f1b
    task_id: OOMPAH-437
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3570a795d41d58af0f79d537e94313eb84d0a150571af2ee9b873b045f057345
    attempts:
    - version: 1
      attempt_id: attempt-b2bec492ab17
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 3570a795d41d58af0f79d537e94313eb84d0a150571af2ee9b873b045f057345
      created_at: '2026-07-31T03:11:34.464955+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T03:11:34.464955+00:00'
      branch_key: OOMPAH-437
      verdict: pass
      completed_at: '2026-07-31T03:19:09.722780+00:00'
      ended_at: '2026-07-31T03:19:09.722780+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-07-31T03:09:25.417445+00:00'
    updated_at: '2026-07-31T03:19:09.722780+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-b2bec492ab17
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3570a795d41d58af0f79d537e94313eb84d0a150571af2ee9b873b045f057345
    created_at: '2026-07-31T03:11:34.464955+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T03:11:34.464955+00:00'
    branch_key: OOMPAH-437
---
## Summary

When a project has YOLO mode enabled, decomposition-generated child tasks must remain Proposed while the decomposition is being applied, then be promoted to Open only after the epic and every child have been created and linked successfully. Preserve non-YOLO behavior and idempotency on retries. Add regression coverage for successful YOLO promotion, failure/partial application (no premature promotion), and non-YOLO projects. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-24 02:44
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-24 02:44
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-24 02:44
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 3
- Tokens: 11 in / 40 out [51 total]
- Cost: $0.0000
- Exit: terminated, Duration: 24s
- Log: OOMPAH-437__20260724T024435Z.jsonl
---
author: oompah
created: 2026-07-24 02:45
---
Implemented and deployed YOLO decomposition finalization. Generated children remain Proposed until every child exists and is linked to the generated epic, then move to Open together. Added complete-link, partial-link safety, retry-idempotence, and YOLO integration regression coverage; make test passed (12,310 tests). Commit 5d724c34c pushed to main.
---
author: oompah
created: 2026-07-24 02:45
---
Implemented and deployed: YOLO-generated decomposition children remain Proposed until every child is created and linked, then are moved to Open. Added complete-link, partial-link safety, retry-idempotence, and integration tests; make test passed (12,310 tests). Commit 5d724c34c is on main.
---
author: oompah
created: 2026-07-31 03:09
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-07-31 03:11
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 03:11
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 03:19
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit_sha: 5d724c34cded8f70d003843049a41cab2e77fd20
- merge_commit_subject: Open YOLO decomposition children after finalization
- merge_commit_branches_containing_include_main: true
- task_file_prev_state_path: .oompah/tasks/merged/OOMPAH-437.md (commit 00a59a2dd)
- task_file_current_path: .oompah/tasks/in-validation/OOMPAH-437.md (commit e8817f1b3)
- impl_file: oompah/epic_proposal.py
- impl_symbols: _promote_decomposition_children_to_open, apply_epic_proposal(promote_children_to_open=False), process_epic_proposal_issue passes True
- tests_added_or_updated: tests/test_epic_proposal.py::test_apply_yolo_proposal_opens_children_only_after_complete_decomposition, tests/test_epic_proposal.py::test_apply_yolo_proposal_does_not_open_partially_linked_children, tests/test_epic_proposal.py::test_process_epic_proposal_auto_decomposes_yolo_project_without_approval
- task_topology: parent=null, children=[], blocked_by=[]
- auto_archive_trigger: Aged Merged auto-archive (closed 7 days ago)
---
author: oompah
created: 2026-07-31 03:19
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 53, Tool calls: 42
- Tokens: 48 in / 8.6K out [8.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 7m 48s
- Log: OOMPAH-437__20260731T031138Z.jsonl
---
<!-- COMMENTS:END -->
