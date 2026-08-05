---
id: OOMPAH-549
type: feature
status: In Validation
priority: 0
title: Expose finish-order lifecycle in UI, prompts, and operator documentation
parent: OOMPAH-545
children: []
blocked_by:
- OOMPAH-546
- OOMPAH-547
- OOMPAH-548
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:11.842687Z'
updated_at: '2026-08-05T19:55:10.581068Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-29b01ffeb6ea
    project_id: proj-14849f1b
    task_id: OOMPAH-549
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2d174d37b36a1c846032b84f31ef09c7cc49582906ac48b611e22dd02deb81e2
    attempts:
    - version: 1
      attempt_id: attempt-7faa086401d7
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 2d174d37b36a1c846032b84f31ef09c7cc49582906ac48b611e22dd02deb81e2
      created_at: '2026-08-05T19:54:57.300095+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T19:54:57.300095+00:00'
      branch_key: OOMPAH-549
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T19:24:38.403019+00:00'
    updated_at: '2026-08-05T19:54:57.300095+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-7faa086401d7
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2d174d37b36a1c846032b84f31ef09c7cc49582906ac48b611e22dd02deb81e2
    created_at: '2026-08-05T19:54:57.300095+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T19:54:57.300095+00:00'
    branch_key: OOMPAH-549
---
## Summary

Update task/epic workflow documentation, bootstrap/AGENTS command references, prompts, dashboard terminology, and API descriptions so blocked_by is presented as Must finish after and start_blocked_by as Cannot start until. Document Ready to Integrate, task submission, cycle recovery, and the distinction between agent completion and task completion. Ensure the UI shows exact dependency and integration wait reasons without normal-operation alerts.

Tests must cover generated bootstrap instructions, prompt contracts, dashboard rendering, OpenAPI descriptions, and status-label catalogs.

Acceptance criteria: agents and operators receive unambiguous instructions, existing command documentation is updated, actionable blocked reasons are visible, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:23
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
author: oompah
created: 2026-07-29 17:57
---
Implementation is complete on epic-OOMPAH-545. Full project gate passed: 13,213 tests passed, 7 skipped. Final rebase, merge, and deployment are in progress; this task remains human-owned and must not be dispatched.
---
author: oompah
created: 2026-07-29 18:15
---
The parent epic OOMPAH-545 merged from epic-OOMPAH-545, but this task was Backlog with work branch unset. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-29 18:17
---
The parent epic OOMPAH-545 merged from epic-OOMPAH-545, but this task was Needs Human with work branch unset. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-29 18:27
---
Implemented in PR #579 and merged to main at 31f8938b8f669a316a830690aaedcc1e0d3834bf. Full GitHub CI passed on Python 3.11, 3.12, and 3.13; focused post-rebase compatibility tests passed.
---
author: oompah
created: 2026-08-05 19:24
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-05 19:55
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 19:55
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
