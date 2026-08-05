---
id: OOMPAH-541
type: bug
status: Archived
priority: 1
title: Use resolved project identity in duplicate-screening task details
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T01:23:36.484044Z'
updated_at: '2026-08-05T05:07:51.145140Z'
work_branch: OOMPAH-541
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/573
review_number: '573'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/573
oompah.review_number: '573'
oompah.work_branch: OOMPAH-541
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-e502fe2b43ed: '2026-08-05T05:07:47.862230+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-541
    target_state: Archived
    evidence_fingerprint: b6e3da817cd8357a40252cb3199c3211b8dc5496a5bac99ffb32310064d7b161
    audit_ids:
    - audit-cfbc20dc56a1
    kind: result
    applied: true
    retired_at: '2026-08-05T05:07:47.862254+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-541
    audit_id: audit-cfbc20dc56a1
    attempt_id: attempt-e502fe2b43ed
    target_state: Archived
    evidence_fingerprint: b6e3da817cd8357a40252cb3199c3211b8dc5496a5bac99ffb32310064d7b161
    status: Archived
    audit_ids:
    - audit-cfbc20dc56a1
    applied: false
    created_at: '2026-08-05T05:07:47.862274+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-cfbc20dc56a1
    project_id: proj-14849f1b
    task_id: OOMPAH-541
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b6e3da817cd8357a40252cb3199c3211b8dc5496a5bac99ffb32310064d7b161
    attempts:
    - version: 1
      attempt_id: attempt-ac5e7e4358b6
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b6e3da817cd8357a40252cb3199c3211b8dc5496a5bac99ffb32310064d7b161
      created_at: '2026-08-05T03:03:58.949953+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T03:03:58.949953+00:00'
      branch_key: OOMPAH-541
      ended_at: '2026-08-05T04:25:55.816726+00:00'
      failure_reason: auditor session abandoned after attempt TTL
    - version: 1
      attempt_id: attempt-f031f0e95ebc
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b6e3da817cd8357a40252cb3199c3211b8dc5496a5bac99ffb32310064d7b161
      created_at: '2026-08-05T04:26:08.304778+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-05T04:26:08.304778+00:00'
      branch_key: OOMPAH-541
      candidate_rotation_count: 1
      ended_at: '2026-08-05T04:46:11.349286+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-e502fe2b43ed
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b6e3da817cd8357a40252cb3199c3211b8dc5496a5bac99ffb32310064d7b161
      created_at: '2026-08-05T04:46:18.828715+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-05T04:46:18.828715+00:00'
      branch_key: OOMPAH-541
      candidate_rotation_count: 2
      verdict: pass
      completed_at: '2026-08-05T05:07:47.862022+00:00'
      ended_at: '2026-08-05T05:07:47.862022+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T02:11:41.611401+00:00'
    updated_at: '2026-08-05T05:07:47.862022+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ac5e7e4358b6
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b6e3da817cd8357a40252cb3199c3211b8dc5496a5bac99ffb32310064d7b161
    created_at: '2026-08-05T03:03:58.949953+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T03:03:58.949953+00:00'
    branch_key: OOMPAH-541
    ended_at: '2026-08-05T04:25:55.816726+00:00'
    failure_reason: auditor session abandoned after attempt TTL
  - version: 1
    attempt_id: attempt-f031f0e95ebc
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b6e3da817cd8357a40252cb3199c3211b8dc5496a5bac99ffb32310064d7b161
    created_at: '2026-08-05T04:26:08.304778+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-05T04:26:08.304778+00:00'
    branch_key: OOMPAH-541
    candidate_rotation_count: 1
    ended_at: '2026-08-05T04:46:11.349286+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-e502fe2b43ed
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b6e3da817cd8357a40252cb3199c3211b8dc5496a5bac99ffb32310064d7b161
    created_at: '2026-08-05T04:46:18.828715+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-05T04:46:18.828715+00:00'
    branch_key: OOMPAH-541
    candidate_rotation_count: 2
oompah.task_costs:
  total_input_tokens: 14
  total_output_tokens: 144
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 14
      output_tokens: 144
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 14
    output_tokens: 144
    cost_usd: 0.0
    recorded_at: '2026-08-05T04:28:11.080717+00:00'
---
## Summary

Triggered by: OOMPAH-540

Production verification after OOMPAH-540 exposed a task-detail-only fingerprint bug. GET /api/v1/issues/OOMPAH-472/detail resolves project_id=proj-14849f1b and returns that ID in the response, but calls _issue_duplicate_screening_summary on the tracker Issue before assigning the resolved project ID. Native Markdown tracker issues do not carry project_id, while duplicate fingerprints include it, so the detail endpoint falsely reports a current no_duplicate record as stale. The board path first assigns project_id and correctly reports checked.\n\nImplementation scope:\n- Ensure the detail endpoint assesses duplicate screening with the resolved project identity without mutating persisted task content.\n- Preserve cross-project lookup behavior and all fingerprint semantics.\n- Add a regression test where a native tracker issue has no project_id, its stored screening record was created with the managed project ID, and the detail response reports checked/required rather than stale.\n- Verify the board and detail representations agree.\n\nAcceptance criteria:\nFor a current stored duplicate-screening record, GET issue detail returns state=checked when project_id is supplied or resolved; material task changes still return stale; cross-project issue resolution remains correct; focused API tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:23
---
Claimed by the current interactive session for immediate implementation and live verification. The human-only label prevents scheduler dispatch while this branch is active.
---
author: oompah
created: 2026-07-29 01:29
---
Implemented the resolved-project identity fix and regression coverage for explicit and cross-project detail lookup plus genuine stale-content preservation. Focused API/dashboard suite: 48 passed. Full suite: 13,095 passed, 7 skipped. Secret and diff checks pass.
---
author: oompah
created: 2026-07-29 01:44
---
Merged in PR #573 (main merge c6c445ccb) and deployed in service instance 0ccb73ac-e871-43d0-8c1e-d23827e4dd27. Live verification: both board and GET issue detail report OOMPAH-472 duplicate_screening state=checked, verdict=no_duplicate, checked_at=2026-07-29T01:21:00.553916Z. OOMPAH-480 remains Open and is currently running duplicate_screening, confirming the queue continues to drain. Focused suite: 48 passed; full suite: 13,095 passed, 7 skipped; CI passed on Python 3.11/3.12/3.13.
---
author: oompah
created: 2026-08-05 02:11
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-05 03:04
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 03:04
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 03:04
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 55s
- Log: OOMPAH-541__20260805T030426Z.jsonl
---
author: oompah
created: 2026-08-05 04:26
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-05 04:26
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 04:28
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 0, Tool calls: 4
- Tokens: 14 in / 144 out [158 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 59s
- Log: OOMPAH-541__20260805T042631Z.jsonl
---
author: oompah
created: 2026-08-05 04:46
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-05 04:46
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
