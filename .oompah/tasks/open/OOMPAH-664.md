---
id: OOMPAH-664
type: task
status: Open
priority: null
title: Make issue-list snapshots advance with canonical state-branch task changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T16:04:06.140108Z'
updated_at: '2026-07-31T18:13:36.258057Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: cb124d284cc953ce215037f31063daa984016881cbf20dd585b575b67d4cd2a9
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 88a5b2d6-43e2-447c-bb43-c8339282022b
  claim_owner: 5a45ba37-2907-4778-ab15-29d9f2087774
  claimed_at: '2026-07-31T18:13:30.754325+00:00'
  claim_expires_at: '2026-07-31T18:43:30.754325+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 0422dd38-d60d-4e36-83b7-4591d717f8be
---
## Summary

Live reproduction on 2026-07-31: the canonical native tracker contained OOMPAH-651 and OOMPAH-655 in Needs Human, and task detail plus task CLI reported those states, while GET /api/v1/issues?project_id=proj-14849f1b returned an empty Needs Human set. This caused an operator recovery pass to miss two authoritative tasks until the state-branch files were inspected directly. Prior OOMPAH-305/306 cache work did not prevent this recurrence. Implementation scope: bind every list/board snapshot to the exact project state-branch generation or commit, invalidate it synchronously after checkpoint and direct status mutations, and ensure list, detail, task CLI, websocket, and canonical Markdown agree. Never silently serve a stale empty lane as fresh; expose the existing stale indicator when a fresh authoritative read is unavailable. Relevant files include oompah/server.py issue snapshot/detail caches, state-branch checkpoint callbacks in oompah/oompah_md_tracker.py, websocket broadcasts, and state-cache regression tests. Required deterministic tests: barrier between a cached list read and Needs Human status moves from a separate tracker instance; checkpoint commit invalidation; two projects isolated; list/detail parity; restart; read failure preserves a stale-marked snapshot rather than claiming an empty current lane. Acceptance: an authoritative status move becomes visible in all read surfaces without TTL delay, OOMPAH-651/655-style tasks cannot disappear from lane queries, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 18:13
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 18:13
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
