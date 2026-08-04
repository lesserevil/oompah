---
id: OOMPAH-520
type: task
status: Archived
priority: null
title: Re-run the branch quality gate when an open review head changes
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T17:49:18.823929Z'
updated_at: '2026-08-04T21:27:52.164385Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.work_branch: epic-OOMPAH-502
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-edf71b014236: '2026-08-04T21:27:36.876685+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-520
    target_state: Archived
    evidence_fingerprint: 2076952ea563505f7fffb4cc9669183c2bfdc2f1c88feb998c00f20722605d9c
    audit_ids:
    - audit-ee3efb94ff66
    kind: result
    applied: true
    retired_at: '2026-08-04T21:27:36.876697+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-520
    audit_id: audit-ee3efb94ff66
    attempt_id: attempt-edf71b014236
    target_state: Archived
    evidence_fingerprint: 2076952ea563505f7fffb4cc9669183c2bfdc2f1c88feb998c00f20722605d9c
    status: Archived
    audit_ids:
    - audit-ee3efb94ff66
    applied: true
    created_at: '2026-08-04T21:27:36.876713+00:00'
    applied_at: '2026-08-04T21:27:49.808109+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-ee3efb94ff66
    project_id: proj-14849f1b
    task_id: OOMPAH-520
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2076952ea563505f7fffb4cc9669183c2bfdc2f1c88feb998c00f20722605d9c
    attempts:
    - version: 1
      attempt_id: attempt-edf71b014236
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 2076952ea563505f7fffb4cc9669183c2bfdc2f1c88feb998c00f20722605d9c
      created_at: '2026-08-04T21:20:30.664945+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:20:30.664945+00:00'
      branch_key: epic-OOMPAH-502
      verdict: pass
      completed_at: '2026-08-04T21:27:36.876507+00:00'
      ended_at: '2026-08-04T21:27:36.876507+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T18:29:36.524473+00:00'
    updated_at: '2026-08-04T21:27:36.876507+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-edf71b014236
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2076952ea563505f7fffb4cc9669183c2bfdc2f1c88feb998c00f20722605d9c
    created_at: '2026-08-04T21:20:30.664945+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:20:30.664945+00:00'
    branch_key: epic-OOMPAH-502
---
## Summary

Problem: _open_epic_main_prs returns through _ensure_epic_in_review_metadata as soon as it finds an existing open epic PR/MR. If a repair commit is pushed after initial review creation, _review_quality_gate_passes is never called for the new exact HEAD even though docs/branch-quality-gates.md promises that a new commit or rebase causes a new run. Forge CI still runs, but the persistent local full-gate invariant and exact-SHA evidence are stale. Implementation: in oompah/orchestrator.py, gate the existing-open-review reconciliation path with _review_quality_gate_passes using the resolved project, epic source branch, and target branch. Reuse cached pass evidence for the same key, run exactly once for a changed head, keep the review open but block YOLO through the existing Needs CI Fix transition on failure, and avoid duplicate comments/runs. Tests: extend tests/test_epic_strategy.py and tests/test_quality_gate.py for existing review unchanged-head reuse, changed-head rerun, failure behavior, and no duplicate review creation. Run focused suites and make test. Acceptance criteria: every open epic review's current head has passing exact-head local evidence before metadata/YOLO reconciliation proceeds; unchanged heads do not rerun; new commits and rebases do; PR #564 remains blocked until the new head passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 17:49
---
Claimed by the current Codex session as an exact-head regression discovered while repairing PR #564. Held from dispatch while I implement it on epic-OOMPAH-502.
---
author: oompah
created: 2026-07-28 17:53
---
Implemented and pushed in commit 3a34d9a3f. Existing open epic reviews now call the persistent branch quality gate before metadata and YOLO reconciliation, so unchanged heads reuse evidence while any new commit/rebase runs once for the new exact SHA. Combined epic/quality focused suite passed 210 tests; exact-head full suite passed 12,618 with 7 skipped in 73.01s.
---
author: oompah
created: 2026-07-28 17:54
---
Made changed heads on existing epic reviews run the persistent exact-head quality gate before review/YOLO reconciliation.
---
author: oompah
created: 2026-07-28 18:02
---
Landed in merged epic PR #564 on main.
---
author: oompah
created: 2026-08-04 18:29
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 21:20
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 21:20
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 21:27
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- implementation_commit: 3a34d9a3f49df65d66bc6503d8bd3c5442132ac9
- commit_title: OOMPAH-520: gate changed open review heads
- commit_on_main: true
- commit_on_origin_main: true
- orchestrator_gate_line: oompah/orchestrator.py:8669
- orchestrator_gate_signature: self._review_quality_gate_passes(project, issue, epic_branch, target_branch)
- new_test: tests/test_epic_strategy.py::TestOpenEpicMainPrs::test_existing_pr_waits_for_changed_head_quality_gate
- quality_gate_tests_present: tests/test_quality_gate.py exercises _review_quality_gate_passes at lines 1514,1547,1582,1699,1746
- merged_pr: #564
- task_previous_state: Merged
- requested_target: Archived
- aging_policy: Aged Merged auto-archive (closed 7 days ago)
---
<!-- COMMENTS:END -->
