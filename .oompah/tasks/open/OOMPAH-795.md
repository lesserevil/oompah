---
id: OOMPAH-795
type: feature
status: Open
priority: 1
title: Expose one why-not-progressing projection and make alerts truthful
parent: OOMPAH-770
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-796
- OOMPAH-779
labels: []
assignee: null
created_at: '2026-08-04T13:59:25.042939Z'
updated_at: '2026-08-06T03:46:30.914436Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: cca5bb79b5ef913d067319f95efd895068f95d98a3219c342eac066a5b54df29
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 43ee695d-c124-4814-a175-9a00676f7418
  claim_owner: 11468835-7c49-48df-a46d-b143af3a940a
  claimed_at: '2026-08-06T03:46:16.822975+00:00'
  claim_expires_at: '2026-08-06T04:16:16.822975+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: fa7f348d-d3fa-463f-8983-d5bfb2cf5ba5
---
## Summary

Make API, dashboard board/detail, queue rows, agent panels, and alerts consume WorkDecision rather than local heuristics. Expose owner, disposition, reason code/text, prerequisites, evidence revision, next reassessment, recovery action, and action_required. Global warnings must contain only operator-actionable conditions; queued work, active repair, retry backoff, audit rotation, CI pending, and capacity waits remain task-local/informational. Preserve WebSocket sequence/full-sync behavior and secret redaction. Required tests: executor/UI parity, alert severity transitions and clearing, stale snapshot resync, compact dashboard rendering, accessibility, auth/redaction, and no warning for normal recovery. Acceptance: operator can answer why any task is idle from one projection and every global warning requires an actual operator action.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 03:19
---
Promoted from Backlog to Open after hard-start prerequisite OOMPAH-796 reached Done. Project is temporarily paused for the graceful cutover; dispatch normally on resume.
---
<!-- COMMENTS:END -->
