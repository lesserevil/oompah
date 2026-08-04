---
id: OOMPAH-503
type: bug
status: Archived
priority: 1
title: Limit automatic duplicate detection to nonterminal tasks
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:05:59.013552Z'
updated_at: '2026-08-04T23:22:46.227195Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 97f1c0a8-978f-4528-98ed-ac08e35f86c1
oompah.work_branch: epic-OOMPAH-502
oompah.task_costs:
  total_input_tokens: 150
  total_output_tokens: 29
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 150
      output_tokens: 29
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 150
    output_tokens: 29
    cost_usd: 0.0
    recorded_at: '2026-07-28T17:44:16.234874+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-d13b2e15b7d9: '2026-08-04T23:22:42.840265+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-503
    target_state: Archived
    evidence_fingerprint: 697eae34dcb1e9831f6ef66f84ad0630845ad65c6288d74fb7a2285a880f6f2f
    audit_ids:
    - audit-705d8c260d82
    kind: result
    applied: true
    retired_at: '2026-08-04T23:22:42.840277+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-503
    audit_id: audit-705d8c260d82
    attempt_id: attempt-d13b2e15b7d9
    target_state: Archived
    evidence_fingerprint: 697eae34dcb1e9831f6ef66f84ad0630845ad65c6288d74fb7a2285a880f6f2f
    status: Archived
    audit_ids:
    - audit-705d8c260d82
    applied: false
    created_at: '2026-08-04T23:22:42.840293+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-705d8c260d82
    project_id: proj-14849f1b
    task_id: OOMPAH-503
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 697eae34dcb1e9831f6ef66f84ad0630845ad65c6288d74fb7a2285a880f6f2f
    attempts:
    - version: 1
      attempt_id: attempt-e767ecd57fbd
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 697eae34dcb1e9831f6ef66f84ad0630845ad65c6288d74fb7a2285a880f6f2f
      created_at: '2026-08-04T21:41:17.253063+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:41:17.253063+00:00'
      branch_key: epic-OOMPAH-502
      ended_at: '2026-08-04T21:48:38.539541+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-d13b2e15b7d9
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 697eae34dcb1e9831f6ef66f84ad0630845ad65c6288d74fb7a2285a880f6f2f
      created_at: '2026-08-04T23:13:20.210718+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T23:13:20.210718+00:00'
      branch_key: epic-OOMPAH-502
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-08-04T23:22:42.840082+00:00'
      ended_at: '2026-08-04T23:22:42.840082+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T18:27:57.286099+00:00'
    updated_at: '2026-08-04T23:22:42.840082+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-e767ecd57fbd
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 697eae34dcb1e9831f6ef66f84ad0630845ad65c6288d74fb7a2285a880f6f2f
    created_at: '2026-08-04T21:41:17.253063+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:41:17.253063+00:00'
    branch_key: epic-OOMPAH-502
    ended_at: '2026-08-04T21:48:38.539541+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-d13b2e15b7d9
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 697eae34dcb1e9831f6ef66f84ad0630845ad65c6288d74fb7a2285a880f6f2f
    created_at: '2026-08-04T23:13:20.210718+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T23:13:20.210718+00:00'
    branch_key: epic-OOMPAH-502
    candidate_rotation_count: 1
---
## Summary

Problem: _apply_duplicate_detection currently fetches both active and terminal task states. Similar Done, Merged, or Archived tasks route new work through a Duplicate Investigator, adding minutes and large prompt replay even though the accepted workflow now defines automatic duplicate detection as active-work collision prevention only.

Implementation: in oompah/orchestrator.py and oompah/focus.py, build each project comparison pool exclusively from canonical nonterminal states. Never fetch or compare configured terminal states, including aliases/case variants. Preserve self-exclusion, focus-complete suppression, active duplicate-candidate handling, per-project tracker routing, bounded candidate scanning, and explicit/manual duplicate_detector focus behavior. Update comments/docs that describe open+closed comparison.

Tests: update tests/test_orchestrator_duplicate_detection.py and tests/test_focus.py. Assert Done, Merged, Archived, and a configured custom terminal alias are absent from the fetched pool and cannot add needs:duplicate_detector; assert Open/In Progress matches still block as duplicate candidates; cover native, GitHub, and GitLab tracker-neutral state lists; run focused tests and make test at the final branch gate.

Acceptance criteria: terminal task history can never trigger automatic duplicate screening or a duplicate-detector agent; active duplicate collisions remain blocked; metrics remain accurate; no tracker performs a terminal-state duplicate query.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:06
---
Claimed for manual implementation by the current Codex session. Held in Backlog while the shared epic branch is built so Oompah does not dispatch another agent; status will move to In Progress and Done as this session completes the slice.
---
author: oompah
created: 2026-07-28 15:07
---
Understanding: automatic duplicate detection will become active-work collision detection only. I will fetch only configured active states, defensively filter any terminal records returned by a tracker, remove the closed-match auto-handoff path, and retain explicit/manual duplicate_detector focus support.
---
author: oompah
created: 2026-07-28 15:10
---
Implemented on epic-OOMPAH-502 in commit 91d6c4344. Automatic duplicate detection now requests only configured active states and defensively removes terminal records returned by over-broad trackers; the former terminal-match duplicate-detector handoff was removed. Focused regression suite: 160 passed.
---
author: oompah
created: 2026-07-28 15:10
---
Terminal tasks are excluded from automatic duplicate detection at query and filtering boundaries; regression tests pass.
---
author: oompah
created: 2026-07-28 17:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 17:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 17:44
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 7
- Tokens: 150 in / 29 out [179 total]
- Cost: $0.0000
- Exit: terminated, Duration: 58s
- Log: OOMPAH-503__20260728T174321Z.jsonl
---
author: oompah
created: 2026-07-28 17:53
---
Restored after patch-equivalent commit 91d6c4344 was verified on the rebased epic branch; terminal-task duplicate filtering remains fully implemented.
---
author: oompah
created: 2026-08-04 18:28
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 23:13
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 23:13
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
