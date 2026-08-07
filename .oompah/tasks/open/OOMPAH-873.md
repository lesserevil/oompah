---
id: OOMPAH-873
type: bug
status: Open
priority: 1
title: Make issue-list and full-sync snapshots match fresh state-branch detail reads
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T05:50:20.335247Z'
updated_at: '2026-08-07T07:17:00.117273Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d1ee86e4ec16c18e915ca678ab368225568d7d5bd26df38fa56b992b965d3f41
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 6fbc6bd7-c569-4912-9b15-b6926f2002ed
  claim_owner: 1f41f145-fc51-4991-b60c-19864fd45ab6
  claimed_at: '2026-08-07T07:16:16.398874+00:00'
  claim_expires_at: '2026-08-07T07:46:16.398874+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 1be8d429-6ceb-4b7f-b928-1b0678cecb43
---
## Summary

Triggered by: OOMPAH-768

Live regression after OOMPAH-664 and OOMPAH-691 through OOMPAH-695: the canonical state-branch file for OOMPAH-768 is .oompah/tasks/in-progress/OOMPAH-768.md with status In Progress and updated_at 2026-08-07T04:20:57Z, and GET issue detail returns In Progress with tracker_state_fresh=true, but repeated GET /api/v1/issues full snapshots publish tracker_state/state Done and place the task in the Done column. Because the authoritative full-sync payload is itself stale, WebSocket gap detection cannot converge the UI. Reproduce and repair the native tracker fetch_all_issues/snapshot cache/source-generation path so list serialization and detail reads share one exact state-branch authority generation. Relevant code: native Markdown tracker read/cache invalidation and atomic status-file moves, server _ensure_issues_snapshot_refresh/_fetch_and_serialize_issues/source generation checks, full-sync response construction. Required tests: status-file move or lifecycle write followed by fresh detail and forced issue snapshot yields identical state; paused projects still refresh API-mutated tracker state; snapshot generation never advances while serving an older task object; concurrent move/read is atomic; WebSocket full sync contains the same state as detail. Acceptance: every full issue snapshot and full-sync response for a reported source revision exactly matches direct detail reads from that revision, so sequence recovery cannot install stale task columns.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

