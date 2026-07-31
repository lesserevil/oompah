---
id: OOMPAH-439
type: task
status: Archived
priority: null
title: Restrict Epic Planner routing to epics or explicit handoffs
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T15:59:50.769146Z'
updated_at: '2026-07-31T16:49:11.855546Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 916707ff-0426-4795-bb29-9b0ca988e585
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-c079451c543c: '2026-07-31T16:49:05.682813+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-439
    target_state: Archived
    evidence_fingerprint: d487725d7a8a2868a9edec0cdc6ab5ef56dc9f14a7ab49db8349bc7d692a5749
    audit_ids:
    - audit-da3077db1b59
    kind: result
    applied: true
    retired_at: '2026-07-31T16:49:05.682826+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-439
    audit_id: audit-da3077db1b59
    attempt_id: attempt-c079451c543c
    target_state: Archived
    evidence_fingerprint: d487725d7a8a2868a9edec0cdc6ab5ef56dc9f14a7ab49db8349bc7d692a5749
    status: Archived
    audit_ids:
    - audit-da3077db1b59
    applied: true
    created_at: '2026-07-31T16:49:05.682846+00:00'
    applied_at: '2026-07-31T16:49:10.978554+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-da3077db1b59
    project_id: proj-14849f1b
    task_id: OOMPAH-439
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d487725d7a8a2868a9edec0cdc6ab5ef56dc9f14a7ab49db8349bc7d692a5749
    attempts:
    - version: 1
      attempt_id: attempt-c079451c543c
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d487725d7a8a2868a9edec0cdc6ab5ef56dc9f14a7ab49db8349bc7d692a5749
      created_at: '2026-07-31T16:44:52.346558+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T16:44:52.346558+00:00'
      branch_key: OOMPAH-439
      verdict: pass
      completed_at: '2026-07-31T16:49:05.682616+00:00'
      ended_at: '2026-07-31T16:49:05.682616+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-07-31T16:44:42.196742+00:00'
    updated_at: '2026-07-31T16:49:05.682616+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-c079451c543c
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d487725d7a8a2868a9edec0cdc6ab5ef56dc9f14a7ab49db8349bc7d692a5749
    created_at: '2026-07-31T16:44:52.346558+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T16:44:52.346558+00:00'
    branch_key: OOMPAH-439
---
## Summary

Prevent keyword-rich ordinary tasks from being routed to Epic Planner. Epic Planner must be eligible only when the issue type is epic or the task has an explicit needs:epic_planner label. Preserve explicit handoffs, and reactivate the Feature Developer focus in .oompah/foci.json so feature tasks have their normal route. Add regression coverage for non-epic keyword matches, explicit handoff override, and epic routing. Run make test and deploy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-24 16:00
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-24 16:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-24 16:00
---
Understanding: screening whether this Epic Planner routing fix duplicates prior work. I will search task history and project docs for Epic Planner eligibility, needs:epic_planner handoffs, and Feature Developer focus routing; inspect plausible tasks in full; then archive only if the same underlying work is already covered, otherwise hand off to implementation without code changes.
---
author: oompah
created: 2026-07-24 16:01
---
Deployed routing guard: Epic Planner now only selects true epics, unless explicitly requested with needs:epic_planner. Reactivated the local Feature Developer focus and added regression coverage for false-positive planning keywords, explicit handoffs, and ordinary epic routing. make test passed (12,314 tests). Commit 9af39f31f pushed to main.
---
author: oompah
created: 2026-07-24 16:02
---
Deployed routing guard: Epic Planner now only selects true epics, unless explicitly requested with needs:epic_planner. Reactivated the local Feature Developer focus and added regression coverage for false-positive planning keywords, explicit handoffs, and ordinary epic routing. make test passed (12,314 tests). Commit 9af39f31f pushed to main.
---
author: oompah
created: 2026-07-31 16:44
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-07-31 16:44
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 16:44
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 16:49
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 9af39f31fbd0ee4985245fd14e8a20cc73d3a289
- merge_subject: Restrict epic planning to epics
- on_main: yes (origin/main contains 9af39f31f)
- focus_test_result: 138 passed, 0 failed (pytest tests/test_focus.py)
- regression_tests_present: test_epic_planner_does_not_match_non_epic_planning_keywords, test_epic_planner_allows_explicit_handoff_for_non_epic, test_epic_planner_selected_for_epic_issue_type, test_epic_planner_selected_by_keyword_epic
- guard_location: oompah/focus.py lines 762-772 within score_focus()
- feature_focus_state: BUILTIN_FOCI entry name='feature' role='Feature Developer' status defaults to 'active'
- working_tree: clean; branch up to date with origin/main
---
<!-- COMMENTS:END -->
