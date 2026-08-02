---
id: OOMPAH-445
type: task
status: Archived
priority: null
title: Keep shared-epic prompt branch aligned with allocated workspace
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-25T20:24:30.180505Z'
updated_at: '2026-08-02T01:34:52.240586Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-07ced114b1ad: '2026-08-02T01:34:48.082622+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-445
    target_state: Archived
    evidence_fingerprint: c375243984516dfccbd6efde7567266647de54288455eec2b34234f7e096704d
    audit_ids:
    - audit-32c1cbfc0fe8
    kind: result
    applied: true
    retired_at: '2026-08-02T01:34:48.082634+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-445
    audit_id: audit-32c1cbfc0fe8
    attempt_id: attempt-07ced114b1ad
    target_state: Archived
    evidence_fingerprint: c375243984516dfccbd6efde7567266647de54288455eec2b34234f7e096704d
    status: Archived
    audit_ids:
    - audit-32c1cbfc0fe8
    applied: false
    created_at: '2026-08-02T01:34:48.082650+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-32c1cbfc0fe8
    project_id: proj-14849f1b
    task_id: OOMPAH-445
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c375243984516dfccbd6efde7567266647de54288455eec2b34234f7e096704d
    attempts:
    - version: 1
      attempt_id: attempt-07ced114b1ad
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c375243984516dfccbd6efde7567266647de54288455eec2b34234f7e096704d
      created_at: '2026-08-02T01:23:35.071987+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:23:35.071987+00:00'
      branch_key: OOMPAH-445
      verdict: pass
      completed_at: '2026-08-02T01:34:48.082459+00:00'
      ended_at: '2026-08-02T01:34:48.082459+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:14:17.349708+00:00'
    updated_at: '2026-08-02T01:34:48.082459+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-07ced114b1ad
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c375243984516dfccbd6efde7567266647de54288455eec2b34234f7e096704d
    created_at: '2026-08-02T01:23:35.071987+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:23:35.071987+00:00'
    branch_key: OOMPAH-445
---
## Summary

Bug observed while recovering EXOCOMP-115: the child already had correct work_branch=epic-EXOCOMP-110 but a stale branch_name=EXOCOMP-115. _create_workspace_for_issue only assigned issue.branch_name inside the conditional that repairs work_branch, so render_prompt told the ACP agent its shared epic worktree was on EXOCOMP-115. The session then switched the shared worktree to that per-task branch, stranding edits from the epic branch.\n\nImplementation scope: in oompah/orchestrator.py, always align the in-memory issue.branch_name to the resolved parent epic branch before rendering/dispatch, even when persisted work_branch is already correct; keep tracker writes conditional on stale work_branch. Add a regression in tests/test_epic_strategy.py covering correct work_branch plus stale/default branch_name and assert both workspace allocation and rendered branch identity use the epic branch. Check related unresolved-parent fallback for the same invariant.\n\nAcceptance criteria: shared-epic prompts never name a per-task branch; dispatch cannot switch the shared worktree away from the epic branch due to stale Issue.branch_name; no unnecessary tracker metadata write occurs when work_branch is already correct; relevant focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-25 20:26
---
Manual repair is in progress in the main checkout. Holding this task out of scheduler dispatch until the regression suite and commit complete so a second agent cannot race the same files.
---
author: oompah
created: 2026-07-25 20:38
---
Fixed shared-epic dispatch so the prompt branch is always aligned with the canonical allocated epic workspace, including unresolved-parent recovery; added regression coverage; full suite passed (12,320 passed, 7 skipped); pushed as 7a7da7704.
---
author: oompah
created: 2026-07-26 00:29
---
Delivery reconciled: shared-epic prompt/workspace branch alignment is present on origin/main in commit 7a7da7704. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:29
---
Verified delivered on origin/main in 7a7da7704 and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:14
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:23
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:23
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:34
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 7a7da77045e08949169a685d39651c63df85768c
- commit_on_origin_main: true
- orchestrator_align_line: oompah/orchestrator.py:11750 issue.branch_name = epic_branch (unconditional)
- orchestrator_fallback_lines: oompah/orchestrator.py:11790-11791 issue.work_branch/branch_name = expected_epic_branch
- regression_test_correct_workbranch: tests/test_epic_strategy.py:1440-1449 (stale branch_name repaired, no tracker write)
- regression_test_unresolved_parent: tests/test_epic_strategy.py:1483-1484 (work_branch and branch_name asserted epic-aligned)
- previous_state: Merged
- aging_signal: auto-archive comment 2026-08-02 01:14 (closed 7 days ago)
---
<!-- COMMENTS:END -->
